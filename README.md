# ScoutLab

本地优先的足球数据研究平台，用公开且合规的数据源完成数据采集、实体对齐、特征工程、球员价值评估、比分预测和可视化报告。

当前仓库已完成 Phase 1–9 的首批实现：已有 Python 工程配置、数据层目录占位、DuckDB 查询入口、Parquet 幂等写入、ingest metadata sidecar、核心表定义草案，以及带缓存、限速、重试和结构化异常的 StatsBomb Open Data、Football-Data.co.uk、Club Elo、Understat、受限 FBref 和 Transfermarkt manual importer，再加上名称标准化、球队/球员 bridge builder、team_match、player_match、team_rolling、player_rolling 的无未来泄露特征第一刀、带时间序列切分与 OOF 预测的身价合理性 baseline，以及独立 Poisson 比分 baseline、比分概率矩阵和最小回测，以及 Streamlit + Plotly 交互式可视化 MVP。后续开发以 `TASKS.md` 作为 roadmap 真源，以 `deep-research-report.md` 作为架构、数据源和合规依据。

## 项目定位

默认 MVP 范围：

- 目标赛事：Big 5 联赛 + UCL/UEL。
- 时间范围：最近 5-10 个赛季。
- 使用场景：本地研究型内部工具，先不做公开多用户产品。
- 存储路线：本地 DuckDB + Parquet，后续需要 API、多用户、权限和索引时再迁移 PostgreSQL。
- 可视化路线：MVP 使用 Streamlit + Plotly；FastAPI、权限控制和批量服务放到扩展阶段。

核心输出不把"球员水平"压成单一神秘分数，而是拆成可解释任务：

- 球员表现分：基于未来贡献代理变量、位置和时间窗口评估球员场上表现。
- 身价合理性：比较球员表现、年龄、合同、联赛强度与市场价值。
- 转会匹配概率：评估球员与俱乐部、联赛、位置需求和价位带的适配。
- 风格 embedding：用标准化后的事件、产出和角色特征生成相似球员与风格聚类。
- 比分预测：作为非核心模块，用 Poisson / Dixon-Coles 建立基线概率模型。

## 数据源策略

数据源按合规性、稳定性、字段价值和可复现性分层。自动采集只允许用于明确可接受的公开接口、静态文件或低风险开放数据。

| 数据源 | 优先级 | 用途 | 策略 |
|---|---:|---|---|
| StatsBomb Open Data | P0 | 事件流、阵容、比赛数据 | 官方公开 JSON，作为事件主源 |
| Football-Data.co.uk | P0 | 比赛结果、赔率基线 | 官方 CSV，作为比分预测与回测基线 |
| Club Elo | P0 | 球队强度时间序列 | 官方 API/CSV，作为球队强度先验 |
| Understat | P1 | xG、xA、xGChain、xGBuildup | 非官方公开端点，需缓存、限速和结构校验 |
| FBref | P1 | 标准表、赛程、补充统计 | 仅低频、受限、缓存使用；不作为 advanced 主源 |
| Transfermarkt | P2 | 市值、合同、转会标签 | 禁止自动抓取；只允许手动或授权导入快照 |

所有采集任务都必须记录来源、URL、请求时间、状态码、缓存命中、解析版本和原始文件哈希，保证结果可回溯。

## 推荐架构

数据层采用 lakehouse 风格的本地分层：

```text
data/
  raw/
    statsbomb_open/
    football_data/
    clubelo/
    understat/
    fbref/
    transfermarkt_manual/
  silver/
    dimensions/
    facts/
    bridge/
  gold/
    marts/
    feature_store/
  models/
    training_sets/
    artifacts/
    oof_predictions/
  reports/
    html/
    pdf/
  logs/
    ingestion/
    validation/
```

源码按以下模块边界组织：

```text
src/scoutlab/
  adapters/      # 数据源采集与手动导入
  entities/      # 名称标准化、球队/球员实体对齐、bridge table
  storage/       # DuckDB/Parquet 读写与后续 PostgreSQL 同步
  features/      # 球员、球队、比赛、市场标签特征
  models/        # 身价合理性、转会匹配、比分预测、embedding
  evaluation/    # 时间序列回测、校准、模型报告
  viz/           # Plotly 图表
  app/           # Streamlit 应用入口
tests/
  unit/
```

## 技术默认值

- 语言：Python。
- 包管理：`uv`。
- 数据存储：Parquet 文件 + DuckDB 查询。
- 数据校验：Pydantic schema、字段检查、源文件哈希。
- 测试：pytest。
- 代码质量：Ruff。
- 可视化：Streamlit + Plotly。
- 模型：scikit-learn 基线优先，后续按需要引入 XGBoost、SHAP、penaltyblog、socceraction。

## 常用命令

```bash
uv sync
uv run pytest
uv run ruff check .
PYTHONPATH=src uv run python -m scoutlab info
PYTHONPATH=src uv run python -m scoutlab ingest
PYTHONPATH=src uv run python -m scoutlab build-features
PYTHONPATH=src uv run python -m scoutlab train
PYTHONPATH=src uv run python -m scoutlab validate
PYTHONPATH=src uv run python -m scoutlab serve
uv run streamlit run src/scoutlab/app/streamlit_app.py
```

## 合规边界

- 不绕过网站条款、登录、验证码、Cloudflare 或反爬机制。
- 不自动抓取 Transfermarkt；市场价值和合同数据只通过手动或授权快照导入。
- 不高频请求 FBref；如使用，必须限速、缓存，并把它视为补充源。
- 不公开分发受限制的原始缓存。
- 不把项目用于赌博营销、规避服务条款或操纵性决策。
