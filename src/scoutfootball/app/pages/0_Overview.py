"""Artifact and model overview page shared with the API-backed frontend."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scoutfootball.api import (
    get_artifacts_summary,
    get_model_runs,
    get_prediction_summary,
)

st.header("总览")

artifacts = get_artifacts_summary()
prediction = get_prediction_summary()
model_runs = get_model_runs()

# --- Summary metrics ---
metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
metric_col1.metric("球员比赛行", f"{artifacts.get('player_match_rows', 0):,}")
metric_col2.metric("球队比赛行", f"{artifacts.get('team_match_rows', 0):,}")
metric_col3.metric("评分行", f"{artifacts.get('rating_rows', 0):,}")
metric_col4.metric("事件样本", f"{artifacts.get('event_samples', 0):,}")

st.caption(f"数据来源状态：{artifacts.get('data_source_label', 'unknown')}")

# --- Data health ---
health = artifacts.get("data_health", {})
health_rows = [
    {
        "信号": "身价 OOF",
        "状态": "HIGH" if health.get("oof_available") else "LOW",
        "说明": "OOF 结果可用于身价偏离页" if health.get("oof_available") else "暂无 OOF 结果",
    },
    {
        "信号": "球员 match 覆盖",
        "状态": "MEDIUM" if health.get("player_match_coverage") else "LOW",
        "说明": health.get("player_match_coverage") or "未发现覆盖说明",
    },
    {
        "信号": "真实标签",
        "状态": "HIGH" if health.get("truth_labels_available") else "LOW",
        "说明": "真实标签表已非空" if health.get("truth_labels_available") else "当前仍为空表模板",
    },
]
st.subheader("数据健康")
st.dataframe(pd.DataFrame(health_rows), use_container_width=True, hide_index=True)

# --- Confidence gate ---
coverage_gate = health.get("confidence_gate", "")
if coverage_gate:
    st.info(f"置信门槛：{coverage_gate}")

# --- Artifact registry ---
artifact_rows = []
for artifact in artifacts.get("artifacts", []):
    updated_at = artifact.get("updated_at")
    artifact_rows.append({
        "产物": artifact.get("label", ""),
        "行数": artifact.get("rows"),
        "存在": artifact.get("exists", False),
        "更新时间": datetime.fromtimestamp(updated_at).isoformat(timespec="seconds")
        if updated_at
        else "—",
        "路径": artifact.get("path", ""),
    })
st.subheader("产物注册表")
st.dataframe(pd.DataFrame(artifact_rows), use_container_width=True, hide_index=True)

# --- Match prediction models ---
if prediction.get("status") == "ok":
    st.subheader("比赛预测模型")

    # Poisson
    pred_cols = st.columns(4)
    pred_cols[0].metric("Poisson 模型", str(prediction.get("model_type", "independent_poisson")))
    pred_cols[1].metric("训练行数", f"{int(prediction.get('train_rows', 0)):,}")
    pred_cols[2].metric("球队数", f"{int(prediction.get('num_teams', 0)):,}")
    pred_cols[3].metric("平滑", str(prediction.get("smoothing", "—")))

    # Dixon-Coles
    dc = prediction.get("dixon_coles", {})
    if dc.get("status") == "ok":
        dc_cols = st.columns(4)
        dc_cols[0].metric("Dixon-Coles", "可用")
        dc_cols[1].metric("rho", f"{dc.get('rho', 0):.4f}")
        dc_cols[2].metric("主场优势", f"{dc.get('home_advantage', 0):.4f}")
        dc_cols[3].metric("训练场次", f"{int(dc.get('num_matches', 0)):,}")
    else:
        st.caption("Dixon-Coles：未可用")
else:
    st.subheader("比赛预测模型")
    st.info("预测模型产物未发现。请先运行 `scoutfootball train`。")

# --- Model runs ---
run_rows = []
for run in model_runs.get("runs", [])[:20]:
    metrics = run.get("metrics", {}) if isinstance(run.get("metrics"), dict) else {}
    run_rows.append({
        "run_id": run.get("run_id", ""),
        "spearman": metrics.get("spearman", run.get("spearman")),
        "pearson": metrics.get("pearson", run.get("pearson")),
        "overfit_gap": metrics.get("overfit_gap", run.get("overfit_gap")),
        "input_hash": run.get("input_hash", ""),
    })
st.subheader("模型运行")
if run_rows:
    st.dataframe(pd.DataFrame(run_rows), use_container_width=True, hide_index=True)
else:
    st.info("当前未发现模型运行登记。")

# --- License attribution ---
licenses = artifacts.get("license_attribution", {})
if licenses:
    st.subheader("数据源许可")
    lic_rows = []
    for key, desc in licenses.items():
        if isinstance(desc, dict):
            lic_rows.append({
                "数据源": desc.get("name", key),
                "许可证": desc.get("license", "—"),
                "署名": "需要" if desc.get("attribution_required") else "不需要",
                "URL": desc.get("url", "—"),
            })
        else:
            lic_rows.append({"数据源": key, "许可证": str(desc), "署名": "—", "URL": "—"})
    if lic_rows:
        st.dataframe(pd.DataFrame(lic_rows), use_container_width=True, hide_index=True)

# --- Available models ---
available = prediction.get("available_models", [])
if available:
    st.caption(f"可用模型：{', '.join(available)}")
