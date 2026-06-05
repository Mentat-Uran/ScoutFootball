# 评分产物持久化与前端数据服务 Spec

## Why
GPU 优化后的参数和球员评分产物目前只保存在 Windows GPU 服务器上，本地无法访问。前端（Streamlit 和 Liquid Glass）需要一个统一的 DuckDB 数据库来查询球员评分，而不是每次从散落的 Parquet 文件读取。

## What Changes
- 新增 GPU 服务器文件下载接口（`/download/<path>`），将 `optimized_params.npy`、`optimized_params_meta.json`、`player_ratings_optimized.parquet` 等产物同步到本地
- 新增 `scoutlab export-ratings` 命令：读取优化参数 + 全量球员特征，计算评分，写入 DuckDB 数据库
- DuckDB 数据库 schema 包含：球员评分表、优化参数元数据表、联赛指标表、球队覆盖表
- Streamlit `data_loader.py` 新增从 DuckDB 加载球员评分的函数
- 前端页面可按位置、联赛、球队筛选球员评分

## Impact
- Affected code:
  - `scripts/gpu_server.py` — 新增 `/download` 端点
  - `scripts/gpu_client.py` — 新增 `download` 子命令
  - `src/scoutlab/__main__.py` — 新增 `export-ratings` 命令入口
  - `src/scoutlab/storage/duckdb_io.py` — 新增评分数据库 schema 和写入函数
  - `src/scoutlab/app/data_loader.py` — 新增 DuckDB 评分加载函数
  - `src/scoutlab/app/pages/` — 现有页面可读取 DuckDB 评分数据

## ADDED Requirements

### Requirement: GPU 服务器文件下载
GPU 服务器 SHALL 提供 `/download/<path>` 端点，允许客户端下载 `data/gold/feature_store/` 和 `data/models/runs/` 下的文件。

#### Scenario: 下载评分产物
- **WHEN** 客户端请求 `GET /download/gold/feature_store/player_ratings_optimized.parquet`
- **THEN** 服务器返回该文件的二进制内容

### Requirement: 评分产物同步到本地
`gpu_client.py` SHALL 新增 `download` 子命令，将 GPU 服务器上的评分产物下载到本地对应目录。

#### Scenario: 同步评分产物
- **WHEN** 运行 `gpu_client.py download`
- **THEN** 本地 `data/gold/feature_store/` 下出现 `optimized_params.npy`、`optimized_params_meta.json`、`player_ratings_optimized.parquet`

### Requirement: 评分导出到 DuckDB
`scoutlab export-ratings` 命令 SHALL 读取优化参数和球员特征数据，计算全量球员评分，写入 DuckDB 数据库 `data/gold/scoutlab.duckdb`。

数据库包含以下表：
- `player_ratings`：球员评分主表（player, team, league, season, position_group, optimized_score, minutes, npg_p90, assists_p90, defense_composite, possession_composite, finishing_shrunk, confidence_level）
- `model_meta`：优化参数元数据（run_id, timestamp, n_params, spearman, pearson, overfit_gap, composite_weights）
- `league_metrics`：各联赛 holdout 指标（league, spearman, pearson, n_teams, coverage）
- `team_coverage`：球队覆盖表（league, season, n_target, n_scored, n_matched, coverage, confidence）

#### Scenario: 导出评分到 DuckDB
- **WHEN** 运行 `scoutlab export-ratings`
- **THEN** 生成 `data/gold/scoutlab.duckdb`，包含上述 4 张表，`player_ratings` 行数与 `player_ratings_optimized.parquet` 一致

### Requirement: 前端从 DuckDB 加载评分
`data_loader.py` SHALL 新增 `load_player_ratings()` 函数，从 DuckDB 读取球员评分，支持按位置、联赛、球队筛选。

#### Scenario: 按位置筛选球员
- **WHEN** 调用 `load_player_ratings(position="ST")`
- **THEN** 返回所有 ST 位置球员的评分 DataFrame，按 optimized_score 降序排列

### Requirement: 评分数据库幂等写入
`export-ratings` 命令 SHALL 幂等执行：如果 DuckDB 已存在，先删除旧表再写入新数据，不追加。

#### Scenario: 重复执行导出
- **WHEN** 连续两次运行 `scoutlab export-ratings`
- **THEN** 第二次运行后数据库内容与第一次完全一致

## MODIFIED Requirements
无修改项。

## REMOVED Requirements
无移除项。
