# 修复代码问题与更新项目文档 Spec

## Why
上一轮 rating-calibration-and-viz 实现了 11 个 Task，但遗留了 pipeline.py 中 4 个 E501 长行 lint 错误，且 README.md、TASKS.md、AGENTS.md 未同步更新，无法反映新增的评分特征矩阵、coverage 置信度、出勤诊断、位置内指标、mplsoccer 集成和 3 个新 Streamlit 页面等能力。

## What Changes
- 修复 `src/scoutlab/pipeline.py` 中 4 个 E501 长行
- 更新 `README.md`：反映新增能力（特征矩阵、mplsoccer、3 个新页面、coverage 置信度、出勤诊断、位置指标、finishing shrinkage）
- 更新 `TASKS.md`：标记 P0/P1 已完成项，更新当前状态描述
- 更新 `AGENTS.md`：更新项目状态、新增模块约定、更新验证命令

## Impact
- Affected specs: 无功能变更，仅修复和文档同步
- Affected code: `src/scoutlab/pipeline.py`（仅格式修复）

## ADDED Requirements
无新增功能需求。

## MODIFIED Requirements

### Requirement: Ruff lint 通过
`src/scoutlab/pipeline.py` 中 4 个 E501 长行 SHALL 被拆分为符合 100 字符限制的格式，使 `uv run ruff check src/` 零错误通过。

### Requirement: README.md 同步
README.md SHALL 反映以下新增能力：
- 评分特征矩阵（rating_feature_matrix.parquet + manifest）
- Coverage 置信度规则（HIGH/MEDIUM/LOW）
- 出勤捷径诊断报告
- 位置内指标和解释模板（8 位置）
- Finishing shrinkage
- mplsoccer 集成（pitch.py、pizza chart）
- 3 个新 Streamlit 页面（Player Rankings、Value Deviation、Match Prediction）
- 低置信度提示集成

### Requirement: TASKS.md 同步
TASKS.md SHALL：
- 标记 P0 中已完成项（特征矩阵契约、缺失字段处理、finishing shrinkage、coverage 低置信度规则、出勤诊断、位置内指标）
- 标记 P1 中已完成项（mplsoccer 集成、3 个核心页面、低置信度提示）
- 更新当前状态描述

### Requirement: AGENTS.md 同步
AGENTS.md SHALL：
- 更新当前项目状态描述
- 新增模块约定（rating_matrix、coverage_confidence、availability_diagnostic、position_metrics、confidence、pitch）
- 更新验证命令

## REMOVED Requirements
无移除项。
