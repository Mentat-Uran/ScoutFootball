"""Match Prediction page: upcoming matches, probabilities, and score distribution.

Supports both Independent Poisson and Dixon-Coles models with a model selector
and a side-by-side comparison view.
"""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scoutfootball.app.data_loader import _parquet_exists, load_team_match
from scoutfootball.evaluation.coverage_confidence import (
    classify_confidence,
    display_confidence_badge,
)
from scoutfootball.models.match_prediction import (
    DixonColesModel,
    IndependentPoissonModel,
    fit_dixon_coles,
    fit_independent_poisson,
    predict_match,
    predict_match_dc,
)

st.header("比赛预测")

team_df = load_team_match()
is_synthetic = team_df.get("is_synthetic", pd.Series(dtype=bool)).any()

# --- Model selector ---
dc_available = _parquet_exists("models/artifacts/dixon_coles_results.parquet")

model_options = ["Poisson"]
if dc_available:
    model_options.append("Dixon-Coles")
    model_options.append("对比 (两者)")

selected_model = st.radio(
    "预测模型",
    model_options,
    index=0,
    horizontal=True,
)

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


# ---------------------------------------------------------------------------
# Model fitting helpers (cached per model type + filtered_df identity)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _fit_poisson_model(_df: pd.DataFrame) -> IndependentPoissonModel:
    return fit_independent_poisson(_df)


@st.cache_resource(show_spinner=False)
def _fit_dc_model(_df: pd.DataFrame) -> DixonColesModel:
    return fit_dixon_coles(_df)


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

# ---------------------------------------------------------------------------
# Helper: fit + predict + validate for a given model type
# ---------------------------------------------------------------------------
from scoutfootball.models.match_prediction import PoissonPrediction  # noqa: E402


def _run_prediction(
    model_type: str,
    df: pd.DataFrame,
    h_id: str,
    a_id: str,
) -> tuple[IndependentPoissonModel | DixonColesModel, PoissonPrediction, set[str]]:
    """Fit the requested model, predict, and return (model, prediction, available_teams).

    Raises ValueError on fit failure or missing teams.
    """
    if model_type == "Dixon-Coles":
        dc_model = _fit_dc_model(df)
        available = set(dc_model.team_attack.keys()) | set(dc_model.team_defense.keys())
        pred = predict_match_dc(dc_model, h_id, a_id)
        return dc_model, pred, available
    else:
        poisson_model = _fit_poisson_model(df)
        available = set(poisson_model.home_attack_strength.keys()) | set(
            poisson_model.away_attack_strength.keys()
        )
        pred = predict_match(poisson_model, h_id, a_id)
        return poisson_model, pred, available


# ---------------------------------------------------------------------------
# Run primary model(s)
# ---------------------------------------------------------------------------
run_comparison = selected_model == "对比 (两者)"

predictions: dict[
    str, tuple[IndependentPoissonModel | DixonColesModel, PoissonPrediction, set[str]]
] = {}
errors: dict[str, str] = {}

model_types_to_run: list[str] = []
if selected_model == "Poisson" or run_comparison:
    model_types_to_run.append("Poisson")
if (selected_model == "Dixon-Coles" or run_comparison) and dc_available:
    model_types_to_run.append("Dixon-Coles")

for mtype in model_types_to_run:
    try:
        predictions[mtype] = _run_prediction(mtype, filtered_df, home_id, away_id)
    except ValueError as exc:
        errors[mtype] = str(exc)

# If the primary (non-comparison) model failed, show error and stop
if not run_comparison:
    primary = model_types_to_run[0]
    if primary in errors:
        st.error(f"{primary} 模型拟合失败：{errors[primary]}")
        st.stop()
    model_obj, prediction, available_teams = predictions[primary]
else:
    # In comparison mode, at least one must succeed
    if not predictions:
        for m, e in errors.items():
            st.error(f"{m} 模型拟合失败：{e}")
        st.stop()
    # Default to the first available for the main display
    first_type = model_types_to_run[0]
    if first_type in predictions:
        model_obj, prediction, available_teams = predictions[first_type]
    else:
        first_type = model_types_to_run[1]
        model_obj, prediction, available_teams = predictions[first_type]

# Validate teams in primary model
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

# --- Model metadata ---
if not run_comparison:
    st.subheader("模型参数")
    if isinstance(model_obj, DixonColesModel):
        m1, m2, m3 = st.columns(3)
        m1.metric("模型", "Dixon-Coles")
        m2.metric("rho (低分修正)", f"{model_obj.rho:.4f}")
        m3.metric("主场优势", f"{model_obj.home_advantage:.4f}")
        c1, c2 = st.columns(2)
        c1.metric("联赛场均进球", f"{model_obj.league_mean_goals:.2f}")
        c2.metric("训练比赛数", f"{model_obj.num_matches}")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("模型", "Independent Poisson")
        m2.metric("联赛主场进球率", f"{model_obj.league_home_rate:.3f}")
        m3.metric("联赛客场进球率", f"{model_obj.league_away_rate:.3f}")

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

# ===========================================================================
# --- Comparison section (both models side by side) ---
# ===========================================================================
if run_comparison and len(predictions) >= 2:
    st.divider()
    st.subheader("📊 模型对比：Poisson vs Dixon-Coles")

    poisson_pred = predictions["Poisson"][1]
    dc_pred = predictions["Dixon-Coles"][1]
    poisson_model: IndependentPoissonModel = predictions["Poisson"][0]  # type: ignore[assignment]
    dc_model: DixonColesModel = predictions["Dixon-Coles"][0]  # type: ignore[assignment]

    # Model parameters comparison
    st.markdown("**模型参数**")
    param_data = {
        "参数": [
            "模型类型",
            "联赛场均进球",
            "主场优势 (rho / home_adv)",
            "训练比赛数",
        ],
        "Poisson": [
            "Independent Poisson",
            f"{poisson_model.league_home_rate:.3f} (主)"
            f" / {poisson_model.league_away_rate:.3f} (客)",
            f"league_home_rate = {poisson_model.league_home_rate:.4f}",
            "—",
        ],
        "Dixon-Coles": [
            "Dixon-Coles",
            f"{dc_model.league_mean_goals:.3f}",
            f"rho = {dc_model.rho:.4f}, home_adv = {dc_model.home_advantage:.4f}",
            f"{dc_model.num_matches}",
        ],
    }
    st.dataframe(pd.DataFrame(param_data), use_container_width=True, hide_index=True)

    # Win/Draw/Loss comparison
    st.markdown("**胜平负概率对比**")
    wdl_data = {
        "结果": ["主胜", "平局", "客胜"],
        "Poisson": [
            f"{poisson_pred.summary.home_win:.1%}",
            f"{poisson_pred.summary.draw:.1%}",
            f"{poisson_pred.summary.away_win:.1%}",
        ],
        "Dixon-Coles": [
            f"{dc_pred.summary.home_win:.1%}",
            f"{dc_pred.summary.draw:.1%}",
            f"{dc_pred.summary.away_win:.1%}",
        ],
    }
    st.dataframe(pd.DataFrame(wdl_data), use_container_width=True, hide_index=True)

    # Expected goals comparison
    st.markdown("**期望进球对比**")
    xg_data = {
        "球队": [f"{home_name} (主)", f"{away_name} (客)"],
        "Poisson": [f"{poisson_pred.home_lambda:.2f}", f"{poisson_pred.away_lambda:.2f}"],
        "Dixon-Coles": [f"{dc_pred.home_lambda:.2f}", f"{dc_pred.away_lambda:.2f}"],
    }
    st.dataframe(pd.DataFrame(xg_data), use_container_width=True, hide_index=True)

    # Market probabilities comparison
    st.markdown("**市场概率对比**")
    market_data = {
        "市场": ["大 2.5 球", "小 2.5 球", "双方进球"],
        "Poisson": [
            f"{poisson_pred.summary.over_2_5:.1%}",
            f"{poisson_pred.summary.under_2_5:.1%}",
            f"{poisson_pred.summary.btts_yes:.1%}",
        ],
        "Dixon-Coles": [
            f"{dc_pred.summary.over_2_5:.1%}",
            f"{dc_pred.summary.under_2_5:.1%}",
            f"{dc_pred.summary.btts_yes:.1%}",
        ],
    }
    st.dataframe(pd.DataFrame(market_data), use_container_width=True, hide_index=True)

    # Side-by-side heatmaps
    st.markdown("**比分分布热力图对比**")
    col_p, col_dc = st.columns(2)

    for col, pred, label in [
        (col_p, poisson_pred, "Poisson"),
        (col_dc, dc_pred, "Dixon-Coles"),
    ]:
        with col:
            st.caption(label)
            sm = pred.score_matrix
            sub_sm = sm.loc[sm.index.isin(range(6)), sm.columns.isin(range(6))]
            fig_cmp = go.Figure(
                go.Heatmap(
                    z=sub_sm.values,
                    x=[str(c) for c in sub_sm.columns],
                    y=[str(i) for i in sub_sm.index],
                    colorscale="Blues",
                    text=[[f"{v:.3f}" for v in row] for row in sub_sm.values],
                    texttemplate="%{text}",
                    hovertemplate="主队 %{y} - 客队 %{x}: %{z:.4f}<extra></extra>",
                )
            )
            fig_cmp.update_layout(
                xaxis_title=f"{away_name} 进球",
                yaxis_title=f"{home_name} 进球",
                height=400,
            )
            st.plotly_chart(fig_cmp, use_container_width=True)

    # --- Score Distribution Comparison (grouped bar chart) ---
    st.markdown("**比分概率分布对比**")

    comparison_scores = [
        (0, 0), (1, 0), (0, 1), (1, 1),
        (2, 0), (0, 2), (2, 1), (1, 2), (2, 2),
        (3, 0), (0, 3), (3, 1), (1, 3), (3, 2), (2, 3), (3, 3),
    ]
    score_labels = [f"{h}-{a}" for h, a in comparison_scores]

    poisson_matrix = poisson_pred.score_matrix
    dc_matrix = dc_pred.score_matrix

    poisson_probs = []
    dc_probs = []
    for h, a in comparison_scores:
        p_val = (
            float(poisson_matrix.loc[h, a])
            if h in poisson_matrix.index and a in poisson_matrix.columns
            else 0.0
        )
        d_val = (
            float(dc_matrix.loc[h, a])
            if h in dc_matrix.index and a in dc_matrix.columns
            else 0.0
        )
        poisson_probs.append(p_val)
        dc_probs.append(d_val)

    fig_score_cmp = go.Figure()
    fig_score_cmp.add_trace(go.Bar(
        x=score_labels,
        y=poisson_probs,
        name="Poisson",
        marker_color="#3498db",
        text=[f"{p:.3f}" for p in poisson_probs],
        textposition="outside",
        textfont=dict(size=9),
    ))
    fig_score_cmp.add_trace(go.Bar(
        x=score_labels,
        y=dc_probs,
        name="Dixon-Coles",
        marker_color="#e74c3c",
        text=[f"{p:.3f}" for p in dc_probs],
        textposition="outside",
        textfont=dict(size=9),
    ))
    fig_score_cmp.update_layout(
        barmode="group",
        xaxis_title="比分 (主-客)",
        yaxis_title="概率",
        yaxis=dict(tickformat=".3f"),
        height=400,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_score_cmp, use_container_width=True)

    # --- Model Difference Summary ---
    st.markdown("**模型差异摘要**")

    p_hw = poisson_pred.summary.home_win
    p_dr = poisson_pred.summary.draw
    p_aw = poisson_pred.summary.away_win
    d_hw = dc_pred.summary.home_win
    d_dr = dc_pred.summary.draw
    d_aw = dc_pred.summary.away_win

    diff_hw = abs(p_hw - d_hw)
    diff_dr = abs(p_dr - d_dr)
    diff_aw = abs(p_aw - d_aw)

    if d_hw > p_hw:
        hw_highlight = f"🔴 Dixon-Coles 给出更高主胜概率 (+{(d_hw - p_hw):.1%})"
    elif p_hw > d_hw:
        hw_highlight = f"🔵 Poisson 给出更高主胜概率 (+{(p_hw - d_hw):.1%})"
    else:
        hw_highlight = "两者主胜概率相同"

    diff_data = {
        "结果": ["主胜", "平局", "客胜"],
        "Poisson": [f"{p_hw:.1%}", f"{p_dr:.1%}", f"{p_aw:.1%}"],
        "Dixon-Coles": [f"{d_hw:.1%}", f"{d_dr:.1%}", f"{d_aw:.1%}"],
        "绝对差异": [f"{diff_hw:.1%}", f"{diff_dr:.1%}", f"{diff_aw:.1%}"],
    }
    st.dataframe(pd.DataFrame(diff_data), use_container_width=True, hide_index=True)
    st.info(hw_highlight)

    # Rho impact: compare low-score probabilities
    st.markdown("**Rho 影响：低比分概率调整**")

    low_scores = [(0, 0), (1, 0), (0, 1), (1, 1)]
    low_score_labels = [f"{h}-{a}" for h, a in low_scores]

    rho_impact_rows = []
    total_poisson_low = 0.0
    total_dc_low = 0.0
    for h, a in low_scores:
        p_val = (
            float(poisson_matrix.loc[h, a])
            if h in poisson_matrix.index and a in poisson_matrix.columns
            else 0.0
        )
        d_val = (
            float(dc_matrix.loc[h, a])
            if h in dc_matrix.index and a in dc_matrix.columns
            else 0.0
        )
        total_poisson_low += p_val
        total_dc_low += d_val
        diff = d_val - p_val
        pct_change = (diff / p_val * 100) if p_val > 0 else 0.0
        rho_impact_rows.append({
            "比分": f"{h}-{a}",
            "Poisson": f"{p_val:.4f}",
            "Dixon-Coles": f"{d_val:.4f}",
            "差异": f"{diff:+.4f}",
            "变化率": f"{pct_change:+.1f}%",
        })

    # Summary row
    total_diff = total_dc_low - total_poisson_low
    total_pct = (total_diff / total_poisson_low * 100) if total_poisson_low > 0 else 0.0
    rho_impact_rows.append({
        "比分": "合计 (0-0~1-1)",
        "Poisson": f"{total_poisson_low:.4f}",
        "Dixon-Coles": f"{total_dc_low:.4f}",
        "差异": f"{total_diff:+.4f}",
        "变化率": f"{total_pct:+.1f}%",
    })

    st.dataframe(pd.DataFrame(rho_impact_rows), use_container_width=True, hide_index=True)

    rho_val = dc_model.rho if hasattr(dc_model, "rho") else 0.0
    if total_diff > 0:
        rho_note = (
            f"rho = {rho_val:.4f}：Dixon-Coles 模型将低比分概率合计"
            f"提高了 {total_pct:+.1f}%，体现了低比分之间的正相关性修正。"
        )
    elif total_diff < 0:
        rho_note = (
            f"rho = {rho_val:.4f}：Dixon-Coles 模型将低比分概率合计"
            f"降低了 {abs(total_pct):.1f}%，体现了低比分之间的相关性修正。"
        )
    else:
        rho_note = f"rho = {rho_val:.4f}：两个模型的低比分概率基本一致。"
    st.caption(rho_note)

    # Top scores comparison
    st.markdown("**最可能比分对比 (Top 5)**")
    for pred, label in [(poisson_pred, "Poisson"), (dc_pred, "Dixon-Coles")]:
        sp: list[tuple[str, float]] = []
        m = pred.score_matrix
        for i in m.index:
            for j in m.columns:
                sp.append((f"{i} - {j}", float(m.loc[i, j])))
        sp.sort(key=lambda x: x[1], reverse=True)
        top5 = sp[:5]
        top5_df = pd.DataFrame(top5, columns=["比分", "概率"])
        top5_df["概率"] = top5_df["概率"].map(lambda p: f"{p:.2%}")
        st.caption(label)
        st.dataframe(top5_df, use_container_width=True, hide_index=True)

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
