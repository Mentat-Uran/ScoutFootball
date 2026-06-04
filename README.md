# ScoutLab

ScoutLab 是本地优先的足球数据研究平台，目标是把公开数据、手动导入数据、可解释球员评分、比赛预测和可视化报告组织成一条可复现的研究流水线。

当前重点不是继续堆爬虫，而是把评分系统升级为可解释、可评估的球探工具：先修真实影响力标签和训练目标，再接入事件动作价值、足球专用可视化和模型卡。

## 当前能力

- Pipeline: `ingest` -> `build-features` -> `train`。
- 数据验证: `scoutlab validate`。
- 本地数据层: DuckDB + Parquet，按 raw/silver/gold/models/reports/logs 分层。
- 球员评分: PyTorch GPU 优化器，当前重点是角色、联赛、出勤和位置偏差校准。
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

## 未来更新策略

P0：评分系统真实影响力校准。重写训练目标，引入 Transfermarkt 手动导入、奖项、专家分档或人工校准集；球队积分相关性只能做辅助校验，不能当主标签。

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

# GPU 远程优化
uv run python scripts/gpu_client.py --server http://192.168.0.189:8420 optimize --pop 32 --steps 500

# Streamlit
uv run streamlit run src/scoutlab/app/streamlit_app.py
```

## 技术栈

Python, uv, DuckDB + Parquet, pandas, scikit-learn, PyTorch, Streamlit, Plotly, FastAPI, pytest, Ruff。后续计划在对应 phase 接入 socceraction 和 mplsoccer。

## 合规边界

- 不绕过验证码或反爬。
- 不自动抓取 Transfermarkt，只做手动或授权导入。
- 不高频请求 FBref。
- 不公开分发受限制的原始缓存。
- 公开展示 StatsBomb Open Data 衍生产物时注明数据源。
- 不把公开事件样本能力写成全量联赛球员能力。
