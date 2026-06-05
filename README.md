# ScoutLab

ScoutLab 是本地优先的足球数据研究平台，目标是把公开数据、手动导入数据、可解释球员评分、比赛预测和可视化报告组织成一条可复现的研究流水线。

当前重点不是继续堆爬虫，而是把评分系统升级为可解释、可评估的球探工具：先修真实影响力标签和训练目标，再接入事件动作价值、足球专用可视化和模型卡。

## 当前能力

- Pipeline: `ingest` -> `build-features` -> `train`。
- 数据验证: `scoutlab validate`。
- 本地数据层: DuckDB + Parquet，按 raw/silver/gold/models/reports/logs 分层。
- 球员评分: PyTorch 权重优化器，已加入 holdout 评估、Pearson 修复、availability cap、ST/W quality cap、稳健球队聚合、team coverage 报告和 2526 N/A 球队过滤；当前重点转向真实影响力标签、训练目标和特征缺失标记重构。
- 真实标签契约: `player_truth_labels.parquet` schema 和校验（`truth_labels.py`），支持 transfermarkt_value/award/expert_tier/manual_calibration 四种标签源。
- 评分模型卡: `MODEL_CARD.md` 记录数据源、标签定义、适用边界、已知偏差和不可用场景。
- 比分预测: Independent Poisson baseline。
- 身价合理性: `value_fairness` OOF 训练产物。
- 产品层: Streamlit 多页 MVP，FastAPI draft 入口。页面包括：
  - Player Rankings: pizza chart、位置内 Top 20、球员详情卡
  - Value Deviation: 实际 vs 预测身价散点图、高估/低估 Top 20
  - Match Prediction: 胜平负概率、比分分布热力图
- 评分特征矩阵: `rating_feature_matrix.parquet` + `rating_feature_matrix_manifest.json`，含缺失字段标记和数据源覆盖。
- Coverage 置信度: HIGH/MEDIUM/LOW 三级，coverage < 0.90 禁止强排序结论。
- 出勤捷径诊断: 置换重要性、位置 availability 权重、出勤驱动球员识别。
- 位置内指标: GK/CB/FB/DM/CM/AM/W/ST 各位置核心维度和 percentile rank。
- Finishing shrinkage: 经验贝叶斯收缩，避免小样本 goals-xG 过度放大。
- mplsoccer 集成: `pitch.py` 封装球场、shot map、pass map、heatmap、pizza chart。
- 低置信度提示: 分钟不足、数据缺失、位置重判不确定、联赛 coverage 低。
- GPU 远程计算: Windows RTX 5070 Ti REST API 脚本。

## 本地数据概览

以下行数来自当前本地文件快速核对，后续以数据文件为准。

| 数据源 | 当前缓存 | 覆盖 |
| --- | ---: | --- |
| FBref standard/shooting/misc | 每表 14,356 行 | 5 赛季 |
| Football-Data raw CSV | 68,953 行 | 10 赛季，20 个 league/division |
| Football-Data `combined_results.parquet` | 待重建 | 需运行 `scripts/rebuild_football_data.py` 重建 10 赛季完整合并缓存 |
| Understat | 31,902 个球员赛季行 | 10 赛季，6 个联赛 |
| StatsBomb Open Data `big5_matches` | 126 场 | 公开比赛样本 |
| StatsBomb Open Data events | 11,871 条事件 | 公开事件样本 |
| player_value_metrics | 10 名样本球员 | StatsBomb 事件价值原型，不代表全量联赛能力 |
| player_ratings_optimized | 27,254 行 | 当前评分产物 |
| player_truth_labels | 空表模板 | 真实影响力标签契约（`truth_labels.py`），待手动填充 |
| rating_feature_matrix | 8,141 行 | 评分特征矩阵，含缺失标记和 fallback |
| rating_feature_matrix_manifest | 1 个 JSON | 特征列元数据、输入 hash 和生成时间 |

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

ScoutLab 的长期路线扩展为 10 层。前 7 层是当前主干，第 8-10 层是球探工作流、预测校准和空间研究扩展，只有在 P0-P4 稳定后逐步推进。

| 层级 | 作用 | 当前状态 |
| --- | --- | --- |
| 数据与合规层 | 本地缓存、手动导入、请求日志、数据质量边界 | 已有基础 |
| 标准事实层 | 统一比赛、球队、球员、阵容、事件、身价、联赛强度 | 已有基础，仍需增强 |
| 跨供应商标准化层 | 内部 event/tracking schema，对齐 SPADL、atomic-SPADL、CDF、kloppy/floodlight 思路 | 远期设计，不急加依赖 |
| 事件动作价值层 | StatsBomb events -> SPADL/atomic-SPADL -> xT -> VAEP/Atomic-VAEP | 计划新增 |
| 球员真值与评分层 | 真实标签 + 赛季统计 + xG/xA + action value + 出勤可靠性 + 联赛强度 + 年龄趋势 | 当前迭代中 |
| 评估与模型卡层 | baseline、时间切分、position-wise metrics、误差分析 | 计划补齐 |
| 产品可视化与 API 层 | Streamlit、Plotly、mplsoccer、FastAPI 只读服务 | Streamlit 8 页，mplsoccer 已接入 |
| 球探决策层 | watchlist、shortlist、人工标签审阅、低置信度复核队列 | 计划新增 |
| 比分预测与概率校准层 | league average -> Independent Poisson -> Dixon-Coles + time decay -> calibration | Poisson 已有，Dixon-Coles 待做 |
| 空间/视频/离球研究层 | StatsBomb 360、Metrica/open tracking、space control、xG+、off-ball value | 远期研究，依赖合规数据 |

## 调研依据

- [socceraction](https://socceraction.readthedocs.io/en/stable/index.html) 已实现 StatsBomb/Wyscout/Opta 到 SPADL/atomic-SPADL 的转换，并包含 xT、VAEP、Atomic-VAEP；ScoutLab 先复用它的建模语言和评估口径。
- [StatsBomb Open Data](https://github.com/statsbomb/open-data) 继续作为事件层第一数据源；公开展示衍生图表或分析时必须注明数据来源。
- [mplsoccer](https://mplsoccer.readthedocs.io/) 适合球场图、radar/pizza chart、heatmap、StatsBomb 坐标可视化，当前已接入。
- [kloppy](https://kloppy.pysport.org/)、[floodlight](https://floodlight.readthedocs.io/en/latest/) 和 [Common Data Format](https://www.cdf.football/) 只作为跨供应商 event/tracking schema 的远期参考，短期不替代当前 Parquet/DuckDB 主干。
- [VAEP 论文](https://arxiv.org/abs/1802.07127)、[xT vs VAEP 对比](https://tomdecroos.github.io/reports/xt_vs_vaep.pdf)、[PlayeRank](https://arxiv.org/abs/1802.04987) 和 2026 年 [combined rating 论文](https://link.springer.com/article/10.1186/s40537-026-01369-w) 支持把评分系统拆成动作价值、角色内排名、真实标签和可解释评估四条线。
- [xG finishing bias 论文](https://arxiv.org/abs/2401.09940) 支持继续使用 shrinkage 和低置信度提示；[Dixon-Coles](https://research-information.bris.ac.uk/en/publications/modelling-association-football-scores-and-inefficiencies-in-the-f/) 只作为比分预测主线的下一档 baseline。

## 评分系统状态

`PROBLEMS.md` 记录的问题已完成第一轮代码级修复：优化器现在只在训练赛季拟合并在 holdout 赛季评估，Pearson 指标不再误用 Spearman p-value，ST/W quality cap 防止前场 quality 绕过 attack，所有位置 availability cap 收敛到 0.18-0.20。

球队赛季评分也不再使用纯分钟加权均值，而是使用 capped minutes + core rotation 的稳健聚合。这样可以减少 Everton、Stuttgart、Hoffenheim、Rennes 这类高分钟中后场球员把球队评分拉高的捷径。

评估报告新增 team coverage。2026-06-05 已用 Football-Data 2025/2026 CSV 直接修补 2526 五大联赛测试集队名，Premier League、La Liga、Bundesliga、Serie A、Ligue 1 的 holdout coverage 均已到 1.00；覆盖低于 0.90 的 league-season 仍只能作为低置信度诊断，不能写成完整前四预测结论。

这些修复只是 guardrail，不等于评分系统已经完成。下一步必须继续在当前电脑先做小规模测试，再视情况重跑完整优化，复盘 2526 holdout 中 Arsenal、Real Madrid、Napoli、PSG 等误差案例，并引入 Transfermarkt 手动导入、奖项、专家分档或人工校准集作为真实球员影响力标签。未经明确允许，不使用远程 5070 Ti 服务器。

新增评分特征矩阵契约：`train` 阶段输出 `rating_feature_matrix.parquet` 和 `rating_feature_matrix_manifest.json`，记录每个特征的数据源、缺失率和填充策略。缺失高阶字段使用位置内中位数填充，不再把缺失值 0 当成真实低能力。Finishing 信号使用经验贝叶斯 shrinkage，小样本射门不过度放大。Coverage 置信度规则：coverage ≥ 0.90 为高置信度，0.70–0.90 为中置信度，< 0.70 为低置信度；中低置信度 league-season 禁止强排序结论。出勤捷径诊断报告可量化 availability 对评分的贡献，识别出勤驱动球员。8 个位置（GK/CB/FB/DM/CM/AM/W/ST）各有核心维度定义和位置内 percentile rank。

神经网络可以作为后续候选评分器，但不能只是把当前球队积分监督目标换成更复杂的 MLP。没有 `player_truth_labels.parquet`、特征缺失标记、时间切分评估和现有优化器 baseline 对比前，神经网络只能作为离线实验，不进入默认评分产物。第一版应优先做浅层模型和多任务目标：球员真实标签排序为主，球队赛季积分相关性只做辅助校验。

## 未来更新策略

P0：评分系统真实影响力校准。先用新 availability cap 和稳健球队聚合重新评估 holdout，重建 Football-Data 10 赛季合并缓存（`scripts/rebuild_football_data.py`），定义真实标签契约（`player_truth_labels.parquet`），输出评分模型卡（`MODEL_CARD.md`），再重写训练目标，引入 Transfermarkt 手动导入、奖项、专家分档或人工校准集；同时补齐特征矩阵、缺失字段标记和神经网络准入门槛。球队积分相关性只能做辅助校验，不能当主标签。

P1：展示增强。引入 mplsoccer，补齐雷达图、pizza chart、shot map、pass map、xT heatmap、位置内榜单和低置信度提示。

P2：事件动作价值。新增 `src/scoutlab/action_value/`，先基于 StatsBomb Open Data 做 xT，输出 `player_action_value.parquet`；xT 稳定后再推进 VAEP。

P3：评分模型重构。把赛季统计、xG/xA、xT/VAEP、出勤可靠性、联赛强度、年龄趋势和置信度合成可解释评分，并输出模型卡；在真实标签层稳定后，增加浅层神经网络候选模型，与当前权重优化器同口径对比。

P4：评估文档。`MODEL_CARD.md` 已输出；补 `EVALUATION.md`，记录 baseline、指标、切分、误差分析、数据覆盖和已知偏差。

P5：比分预测升级。保留 Independent Poisson baseline，再做 Dixon-Coles + time decay，并用 log loss、Brier score、RPS 对比。

P6：跨供应商标准化。先设计内部 event/tracking schema 和数据源 license manifest，再评估 kloppy、floodlight、CDF 是否作为转换工具或 schema 对照。

P7：球探决策层。围绕真实标签、误差案例和低置信度球员建立人工审阅队列、watchlist、shortlist 和可复现报告。

P8：空间/视频/离球研究。StatsBomb 360、Metrica/open tracking、space control、xG+、off-ball value 只在事件价值层和评估层稳定且数据合规后再进入。

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

Python, uv, DuckDB + Parquet, pandas, scikit-learn, Streamlit, Plotly, mplsoccer, FastAPI, pytest, Ruff。PyTorch 已用于评分优化/GPU 脚本；若把神经网络纳入主项目，必须同步更新 `pyproject.toml`、锁文件、训练入口、模型产物和评估文档。后续计划在对应 phase 接入 socceraction。

## 合规边界

- 不绕过验证码或反爬。
- 不自动抓取 Transfermarkt，只做手动或授权导入。
- 不高频请求 FBref。
- 不公开分发受限制的原始缓存。
- 公开展示 StatsBomb Open Data 衍生产物时注明数据源。
- 不把公开事件样本能力写成全量联赛球员能力。
