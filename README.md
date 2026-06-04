# ScoutLab

ScoutLab 是本地优先的足球数据研究平台，目标是把公开数据、手动导入数据、可解释球员评分、比赛预测和可视化报告组织成一条可复现的研究流水线。

当前重点不是继续堆爬虫，而是把评分系统升级为可解释、可评估的球探工具：先修真实影响力标签和训练目标，再接入事件动作价值、足球专用可视化和模型卡。

## 当前能力

- Pipeline: `ingest` -> `build-features` -> `train`。
- 数据验证: `scoutlab validate`。
- 本地数据层: DuckDB + Parquet，按 raw/silver/gold/models/reports/logs 分层。
- 球员评分: PyTorch 优化器，已加入 holdout 评估、Pearson 修复、availability cap、ST/W quality cap、稳健球队聚合和 team coverage 报告；当前重点转向真实影响力标签和训练目标重构。
- 比分预测: Independent Poisson baseline。
- 身价合理性: `value_fairness` OOF 训练产物。
- 产品层: Streamlit 多页 MVP，FastAPI draft 入口。
- GPU 远程计算: Windows RTX 5070 Ti REST API 脚本。

## 本地数据概览

以下行数来自当前本地 Parquet 快速核对，后续以数据文件为准。

| 数据源 | 当前缓存 | 覆盖 |
| --- | ---: | --- |
| FBref standard/shooting/misc | 每表 14,356 行 | 5 赛季 |
| Football-Data | 68,953 个 match-key 行 | 10 赛季，20 个 league/division |
| Understat | 31,902 个球员赛季行 | 10 赛季，6 个联赛 |
| StatsBomb Open Data matches | 126 场 | 公开比赛样本 |
| StatsBomb Open Data events | 11,871 条事件 | 公开事件样本 |
| player_ratings_optimized | 27,254 行 | 当前评分产物 |

### 爬虫运行环境

部分数据源需要特定运行环境：

| 数据源 | 运行要求 | 建议环境 |
| --- | --- | --- |
| FBref (soccerdata) | Chrome + Selenium | Windows GPU 服务器 |
| WhoScored / SofaScore / SoFIFA | Chrome + Selenium | Windows GPU 服务器 |
| Capology | ScraperFC + Chrome | Windows GPU 服务器 |
| StatsBomb | 稳定网络（下载量大） | 运行 `scripts/fetch_statsbomb_full.py` |
| Transfermarkt-datasets | 手动下载 DuckDB | 放到 `data/raw/transfermarkt_datasets/` |
| API-Football | API Key (`API_FOOTBALL_KEY`) | 任意环境，免费 100 请求/天 |

运行 soccerdata 脚本需设置环境变量：
```bash
SOCCERDATA_DIR=./data/soccerdata uv run python scripts/fetch_fbref_10seasons.py
```

## 顶层架构

| 层级 | 作用 | 当前状态 |
| --- | --- | --- |
| 数据与合规层 | 本地缓存、手动导入、请求日志、数据质量边界 | 已有基础 |
| 标准事实层 | 统一比赛、球队、球员、阵容、事件、身价、联赛强度 | 已有基础，仍需增强 |
| 事件动作价值层 | StatsBomb events -> SPADL/atomic-SPADL -> xT -> VAEP | 计划新增 |
| 球员评分层 | 赛季统计 + xG/xA + action value + 出勤 + 联赛强度 + 趋势 | 当前迭代中 |
| 评估与模型卡层 | baseline、时间切分、position-wise metrics、误差分析 | 计划补齐 |
| 产品可视化层 | Streamlit、Plotly、mplsoccer 足球图表 | Streamlit 已有，mplsoccer 待接入 |
| 比分预测层 | league average -> Independent Poisson -> Dixon-Coles | Poisson 已有，Dixon-Coles 待做 |

## 评分系统状态

`PROBLEMS.md` 记录的问题已完成第一轮代码级修复：优化器现在只在训练赛季拟合并在 holdout 赛季评估，Pearson 指标不再误用 Spearman p-value，ST/W quality cap 防止前场 quality 绕过 attack，所有位置 availability cap 收敛到 0.18-0.20。

球队赛季评分也不再使用纯分钟加权均值，而是使用 capped minutes + core rotation 的稳健聚合。这样可以减少 Everton、Stuttgart、Hoffenheim、Rennes 这类高分钟中后场球员把球队评分拉高的捷径。

评估报告新增 team coverage。2026-06-05 已用 Football-Data 2025/2026 CSV 直接修补 2526 五大联赛测试集队名，Premier League、La Liga、Bundesliga、Serie A、Ligue 1 的 holdout coverage 均已到 1.00；覆盖低于 0.90 的 league-season 仍只能作为低置信度诊断，不能写成完整前四预测结论。

这些修复只是 guardrail，不等于评分系统已经完成。下一步必须继续在当前电脑先做小规模测试，再视情况重跑完整优化，复盘 2526 holdout 中 Arsenal、Real Madrid、Napoli、PSG 等误差案例，并引入 Transfermarkt 手动导入、奖项、专家分档或人工校准集作为真实球员影响力标签。未经明确允许，不使用远程 5070 Ti 服务器。

## 未来更新策略

P0：评分系统真实影响力校准。先用新 availability cap 和稳健球队聚合重新评估 holdout，再重写训练目标，引入 Transfermarkt 手动导入、奖项、专家分档或人工校准集；球队积分相关性只能做辅助校验，不能当主标签。

P1：展示增强。引入 mplsoccer，补齐雷达图、pizza chart、shot map、pass map、xT heatmap、位置内榜单和低置信度提示。

P2：事件动作价值。新增 `src/scoutlab/action_value/`，先基于 StatsBomb Open Data 做 xT，输出 `player_action_value.parquet`；xT 稳定后再推进 VAEP。

P3：评分模型重构。把赛季统计、xG/xA、xT/VAEP、出勤可靠性、联赛强度、年龄趋势和置信度合成可解释评分，并输出模型卡。

P4：评估文档。新增 `EVALUATION.md` 和 `MODEL_CARD.md`，记录 baseline、指标、切分、误差分析、数据覆盖和已知偏差。

P5：比分预测升级。保留 Independent Poisson baseline，再做 Dixon-Coles + time decay，并用 log loss、Brier score、RPS 对比。

P6：远期研究。kloppy、floodlight、xG+、tracking data 只在事件价值层和评估层稳定后再考虑。

## 快速开始

```bash
uv sync

# 项目信息
PYTHONPATH=src uv run python -m scoutlab info

# Pipeline
PYTHONPATH=src uv run python -m scoutlab ingest
PYTHONPATH=src uv run python -m scoutlab build-features
PYTHONPATH=src uv run python -m scoutlab train
PYTHONPATH=src uv run python -m scoutlab validate

# 本地评分优化
PYTHONPATH=src uv run python scripts/optimize_ratings_gpu.py --data_dir ./data --pop 10 --steps 300

# 当前电脑小规模 smoke test（不使用远程 5070 Ti 服务器）
PYTHONPATH=src uv run python scripts/optimize_ratings_gpu.py --data_dir ./data --pop 2 --steps 20 --cv-folds 0 --stability-runs 0 --importance-repeats 0

# GPU 远程优化
uv run python scripts/gpu_client.py --server http://192.168.0.189:8420 optimize --pop 32 --steps 500

# Streamlit
uv run streamlit run src/scoutlab/app/streamlit_app.py
```

## 截图

> 以下截图来自 Streamlit 本地运行，数据为当前本地缓存。

| 球员雷达/排名 | 身价偏离榜 | 比赛预测 |
| --- | --- | --- |
| ![球员雷达](screenshots/player_radar.png) | ![身价偏离](screenshots/value_deviation.png) | ![比赛预测](screenshots/match_prediction.png) |

| Top 100 榜单 | 球员详情页 |
| --- | --- |
| ![Top 100](screenshots/top100.png) | ![球员详情](screenshots/player_detail.png) |

## 如何复现 demo 数据

以下步骤在 macOS/Linux 环境下，从零构建与当前本地缓存一致的数据集：

```bash
# 1. 克隆仓库并安装依赖
git clone <repo-url> && cd scoutlab
uv sync

# 2. 确认环境变量（可选，无 Key 时对应源会跳过）
export API_FOOTBALL_KEY=your_key_here
export SOCCERDATA_DIR=./data/soccerdata

# 3. 运行完整 Pipeline
PYTHONPATH=src uv run python -m scoutlab ingest
PYTHONPATH=src uv run python -m scoutlab build-features
PYTHONPATH=src uv run python -m scoutlab train

# 4. 验证数据产物
PYTHONPATH=src uv run python -m scoutlab validate

# 5. 启动 Streamlit 查看结果
uv run streamlit run src/scoutlab/app/streamlit_app.py
```

注意事项：

- 首次 `ingest` 会下载大量数据（FBref、Understat、Football-Data、StatsBomb），预计 10–30 分钟，取决于网络。
- 需要 Chrome + Selenium 的数据源（FBref soccerdata、WhoScored、SofaScore、SoFIFA、Capology）在无头 macOS 下可能失败，建议在 Windows GPU 服务器运行。
- Transfermarkt 需要手动下载 DuckDB 文件放到 `data/raw/transfermarkt_datasets/`。
- 如果某数据源不可用，Pipeline 会跳过并记录日志，不影响其他源。
- 最终产物写 `data/gold/feature_store/` 和 `data/models/`。

## 技术栈

Python, uv, DuckDB + Parquet, pandas, scikit-learn, PyTorch, Streamlit, Plotly, FastAPI, pytest, Ruff。后续计划在对应 phase 接入 socceraction 和 mplsoccer。

## 合规边界

- 不绕过验证码或反爬。
- 不自动抓取 Transfermarkt，只做手动或授权导入。
- 不高频请求 FBref。
- 不公开分发受限制的原始缓存。
- 公开展示 StatsBomb Open Data 衍生产物时注明数据源。
- 不把公开事件样本能力写成全量联赛球员能力。
