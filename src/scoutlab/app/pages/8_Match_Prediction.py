"""Match Prediction page: upcoming matches, probabilities, and score distribution."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scoutlab.app.data_loader import load_team_match
from scoutlab.evaluation.coverage_confidence import classify_confidence, display_confidence_badge
from scoutlab.models.match_prediction import fit_independent_poisson, predict_match

st.header("比赛预测")

team_df = load_team_match()
is_synthetic = team_df.get("is_synthetic", pd.Series(dtype=bool)).any()

# --- League filter ---
league_col = None
for candidate in ("competition_id", "league", "division"):
    if candidate in team_df.columns:
        league_col = candidate
        break

if league_col is not None:
    leagues = sorted(team_df[league_col].dropna().unique())
    selected_league = st.selectbox("联赛", ["全部"] + leagues, index=0)
    if selected_league != "全部":
        filtered_df = team_df[team_df[league_col] == selected_league]
    else:
        filtered_df = team_df
else:
    filtered_df = team_df

# --- Build team list ---
team_names = (
    sorted(filtered_df["team_name"].dropna().unique())
    if "team_name" in filtered_df.columns
    else sorted(filtered_df["team_id"].dropna().astype(str).unique())
)

if len(team_names) < 2:
    st.warning("至少需要两支球队才能进行比赛预测。")
    st.stop()

# --- Match selector ---
match_options = [f"{h} vs {a}" for i, h in enumerate(team_names) for a in team_names[i + 1 :]]
selected_match = st.selectbox("选择对阵", match_options, index=0)
home_name = selected_match.split(" vs ")[0]
away_name = selected_match.split(" vs ")[1]

# --- Fit model ---
try:
    model = fit_independent_poisson(filtered_df)
except ValueError as exc:
    st.error(f"模型拟合失败：{exc}")
    st.stop()

# Resolve team_id from team_name
team_id_map: dict[str, str] = {}
if "team_name" in filtered_df.columns and "team_id" in filtered_df.columns:
    for _, row in filtered_df.drop_duplicates("team_name").iterrows():
        team_id_map[row["team_name"]] = str(row["team_id"])
else:
    for tid in filtered_df["team_id"].dropna().astype(str).unique():
        team_id_map[tid] = tid

home_id = team_id_map.get(home_name, home_name)
away_id = team_id_map.get(away_name, away_name)

# Check team coverage in model
available_teams = set(model.home_attack_strength.keys()) | set(model.away_attack_strength.keys())
home_in_model = home_id in available_teams
away_in_model = away_id in available_teams

if not home_in_model or not away_in_model:
    missing = []
    if not home_in_model:
        missing.append(home_name)
    if not away_in_model:
        missing.append(away_name)
    st.error(f"以下球队不在模型中：{', '.join(missing)}。请选择其他球队。")
    st.stop()

# --- Predict ---
prediction = predict_match(model, home_id, away_id)

# --- Win/Draw/Loss probability bars ---
st.subheader("胜平负概率")

hw = prediction.summary.home_win
dr = prediction.summary.draw
aw = prediction.summary.away_win

fig_bar = go.Figure()
fig_bar.add_trace(
    go.Bar(
        orientation="h",
        y=[""],
        x=[hw],
        name=f"主胜 {hw:.1%}",
        marker_color="#2ecc71",
        text=f"{hw:.1%}",
        textposition="inside",
    )
)
fig_bar.add_trace(
    go.Bar(
        orientation="h",
        y=[""],
        x=[dr],
        name=f"平局 {dr:.1%}",
        marker_color="#f39c12",
        text=f"{dr:.1%}",
        textposition="inside",
    )
)
fig_bar.add_trace(
    go.Bar(
        orientation="h",
        y=[""],
        x=[aw],
        name=f"客胜 {aw:.1%}",
        marker_color="#e74c3c",
        text=f"{aw:.1%}",
        textposition="inside",
    )
)
fig_bar.update_layout(
    barmode="stack",
    showlegend=True,
    xaxis=dict(tickformat=".0%", range=[0, 1]),
    yaxis_visible=False,
    height=120,
    margin=dict(l=10, r=10, t=30, b=10),
)
st.plotly_chart(fig_bar, use_container_width=True)

# --- Most likely scores ---
st.subheader("最可能比分 (Top 10)")

matrix = prediction.score_matrix
score_probs: list[tuple[str, float]] = []
for i in matrix.index:
    for j in matrix.columns:
        score_probs.append((f"{i} - {j}", float(matrix.loc[i, j])))
score_probs.sort(key=lambda x: x[1], reverse=True)

top_scores = score_probs[:10]
score_df = pd.DataFrame(top_scores, columns=["比分", "概率"])
score_df["概率"] = score_df["概率"].map(lambda p: f"{p:.2%}")
st.dataframe(score_df, use_container_width=True, hide_index=True)

# --- Score distribution heatmap (0-5 x 0-5) ---
st.subheader("比分分布热力图")

sub_matrix = matrix.loc[
    matrix.index.isin(range(6)), matrix.columns.isin(range(6))
]

fig_heat = go.Figure(
    go.Heatmap(
        z=sub_matrix.values,
        x=[str(c) for c in sub_matrix.columns],
        y=[str(i) for i in sub_matrix.index],
        colorscale="Blues",
        text=[[f"{v:.3f}" for v in row] for row in sub_matrix.values],
        texttemplate="%{text}",
        hovertemplate="主队 %{y} - 客队 %{x}: %{z:.4f}<extra></extra>",
    )
)
fig_heat.update_layout(
    xaxis_title=f"{away_name} 进球",
    yaxis_title=f"{home_name} 进球",
    height=450,
)
st.plotly_chart(fig_heat, use_container_width=True)

# --- Expected goals ---
st.caption(f"期望进球 — 主队: {prediction.home_lambda:.2f}  客队: {prediction.away_lambda:.2f}")

# --- Market probabilities ---
st.subheader("市场概率")
c1, c2, c3 = st.columns(3)
c1.metric("大 2.5 球", f"{prediction.summary.over_2_5:.1%}")
c2.metric("小 2.5 球", f"{prediction.summary.under_2_5:.1%}")
c3.metric("双方进球", f"{prediction.summary.btts_yes:.1%}")

# --- Model confidence ---
st.subheader("模型置信度")

if "match_id" in filtered_df.columns:
    n_matches = len(filtered_df.drop_duplicates(subset=["match_id"]))
else:
    n_matches = len(filtered_df) // 2
n_teams = len(available_teams)

coverage = min(n_teams / max(n_teams, 1), 1.0) if n_teams > 0 else 0.0
confidence = classify_confidence(coverage)

c1, c2 = st.columns(2)
c1.metric("训练比赛数", f"{n_matches}")
c2.metric("模型球队数", f"{n_teams}")

display_confidence_badge(confidence)

if is_synthetic:
    st.warning("当前使用合成演示数据，预测结果仅供参考。")

if n_matches < 50:
    st.warning("训练数据较少，预测置信度较低。")
