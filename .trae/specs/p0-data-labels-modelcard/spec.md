# P0 数据层补齐、真实标签契约与评分模型卡 Spec

## Why

当前评分系统的训练目标仍主要依赖球队积分相关性，缺少球员级真实影响力标签；Football-Data 合并缓存只覆盖 5 大联赛 3 赛季（5,330 行），远低于原始 CSV 的 68,953 行；2526 测试集中部分球队积分 N/A 影响评估；缺少模型卡导致模型边界和偏差不透明。这四个问题共同阻碍评分系统从"能跑"升级为"可评估"。

## What Changes

- 重建 Football-Data 10 赛季 `combined_results.parquet`，从 5,330 行扩展到覆盖全部 20 个 league/division × 10 赛季，保留 2526 alias patch。
- 补全 2526 Football-Data 覆盖：在评估流程中剔除积分 N/A 球队，避免把数据缺口误判为模型错误。
- 定义真实标签数据契约：`player_truth_labels.parquet` 的 schema、校验脚本和空表模板，字段包括 `label_source`、`label_confidence`、`as_of_date`、`position_scope`、`manual_review_flag`，区分身价代理、奖项荣誉、专家分档和人工校准。
- 输出评分模型卡 `MODEL_CARD.md`：数据源、标签定义、适用边界、已知偏差、不可用场景、低置信度球员处理规则。

## Impact

- Affected specs: P0 评分系统真实影响力校准
- Affected code:
  - `src/scoutlab/adapters/football_data.py` — 重建合并逻辑
  - `src/scoutlab/pipeline.py` — 集成新合并和评估过滤
  - `src/scoutlab/features/rating_matrix.py` — 标签字段预留
  - 新增 `src/scoutlab/evaluation/truth_labels.py` — 标签契约和校验
  - 新增 `scripts/rebuild_football_data.py` — 重建脚本
  - 新增 `data/gold/feature_store/player_truth_labels.parquet` — 空表模板
  - 新增 `MODEL_CARD.md` — 评分模型卡
- Affected docs: README.md、TASKS.md、AGENTS.md 需同步更新

## ADDED Requirements

### Requirement: Football-Data 10 赛季完整合并缓存

系统 SHALL 提供一个重建脚本，将 `data/raw/football_data/` 下所有 CSV（10 赛季、20 个 league/division）合并为 `data/raw/football_data/combined_results.parquet`，输出 raw CSV 总行数、active Parquet 行数、league-season 覆盖和输入 hash。

#### Scenario: 重建成功

- **WHEN** 用户运行 `scripts/rebuild_football_data.py`
- **THEN** 生成 `combined_results.parquet`，行数接近 68,953（原始 CSV 总行数减去解析失败行），league-season 覆盖为 20 league/division × 10 赛季
- **AND** 输出重建元数据（行数、league-season 列表、输入 hash、重建时间）

#### Scenario: 保留 alias patch

- **WHEN** 重建完成
- **THEN** 2526 五大联赛队名 alias patch 仍然生效，holdout coverage 维持 1.00

### Requirement: 2526 评估覆盖补全

系统 SHALL 在评估流程中自动剔除积分 N/A 球队，确保评估指标不受数据缺口干扰。

#### Scenario: N/A 球队剔除

- **WHEN** 评估函数读取 2526 测试集
- **THEN** 积分字段为 N/A 的球队不参与 Spearman/Pearson 计算
- **AND** 评估报告标注剔除的球队数量和原因

### Requirement: 真实标签数据契约

系统 SHALL 定义 `player_truth_labels.parquet` 的 schema 和校验脚本，输出空表模板。

#### Scenario: Schema 定义

- **WHEN** 标签契约模块被导入
- **THEN** 可获取 schema 定义，包含字段：`player_id`、`season`、`label_source`（枚举：transfermarkt_value、award、expert_tier、manual_calibration）、`label_confidence`（枚举：high/medium/low）、`label_value`（float）、`as_of_date`、`position_scope`、`manual_review_flag`（bool）

#### Scenario: 校验脚本

- **WHEN** 用户向 `player_truth_labels.parquet` 写入标签数据
- **THEN** 校验脚本检查 schema 一致性、label_source 枚举值、label_confidence 枚举值、无重复 player_id+season+label_source 记录

#### Scenario: 空表模板

- **WHEN** 运行 `scoutlab build-features`
- **THEN** 输出 `data/gold/feature_store/player_truth_labels.parquet` 空表（0 行，正确 schema），供后续手动填充

### Requirement: 评分模型卡

系统 SHALL 输出 `MODEL_CARD.md`，说明当前评分模型的完整信息。

#### Scenario: 模型卡内容

- **WHEN** `MODEL_CARD.md` 被读取
- **THEN** 包含以下章节：数据源、标签定义、适用边界、已知偏差、不可用场景、低置信度球员处理规则、特征维度说明、训练/评估切分方式

## MODIFIED Requirements

### Requirement: Pipeline 集成

`scoutlab build-features` SHALL 在输出中包含重建后的 `combined_results.parquet` 路径和行数信息，以及 `player_truth_labels.parquet` 空表模板。

### Requirement: 评估流程

`scoutlab train` 的评估输出 SHALL 自动剔除积分 N/A 球队，并在 team coverage 报告中标注剔除数量。
