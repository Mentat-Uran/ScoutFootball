# ScoutFootball — Local-First Football Analytics & Player Research

> **本地优先、开放源代码、个人维护、非盈利的足球分析工具箱。**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-Fast-magenta)](https://github.com/astral-sh/uv)
[![DuckDB](https://img.shields.io/badge/DuckDB-Fast%20Analytics-yellow)](https://duckdb.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-Optimized-ee4c2c)](https://pytorch.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B)](https://streamlit.io/)

**[English](../README.md)** | **中文**

---

## 足球分析与球员研究

ScoutFootball 将可复现的数据工作流、球员评分研究、比赛分析和战术工具组织在一个本地优先的研究工作台中，帮助你理解球员表现、球队差异和模型不确定性。

## 它做什么

ScoutFootball 是本地优先、开放源代码、个人维护、非盈利的足球分析与研究项目，把公开数据、合法手动导入、可解释球员评分和比赛预测组织成主要在用户自己设备上运行的可复现工作流。

项目不按 SaaS、付费产品、企业平台或数据市场开发。代码和文档遵循仓库的 MIT License；第三方数据和视频仍遵循各自许可。项目定位和决策规则以 [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) 为准。

世界杯是参考场景包，不是核心平台的永久边界。当前第一参考用途是可复现的本地个人球员评分研究系统；招募、比赛准备、动作价值和赛事工具应复用评分研究的证据内核，而不是各自扩张为独立产品面。

当前重点：让球员评分研究具备明确目标、canonical 身份和数据粒度、透明 baseline、独立评价标签、不确定性、active rating 新鲜度、错误分析和可重放本地研究包。详细缺陷和依赖门禁见 [`PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`](PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md)。

## 战略与真实范围

- [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) 定义本地、开放、个人、非盈利的项目属性，优先级高于其他规划文档。
- [`PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`](PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md) 定义当前球员评分研究缺陷、目标系统、功能积压和 PRS-0 至 PRS-8 门禁。
- [`CAPABILITIES.md`](CAPABILITIES.md) 区分已交付、部分交付、样例/实验、本地状态、计划和未核验能力。
- [`FOOTBALL_TOOLING_LANDSCAPE_2026.md`](FOOTBALL_TOOLING_LANDSCAPE_2026.md) 给出 2026 商业与开放工具版图，作为技术参照，不是商业化或市场进入计划。
- [`ROADMAP.md`](ROADMAP.md) 只定义有退出门槛的长期依赖顺序，不设置日历期限；[`TASKS.md`](TASKS.md) 顶部是当前可执行队列。

## 核心能力

- **研发流水线:** `ingest` -> `build-features` -> `train`。
- **数据验证:** `scoutfootball validate` 检查训练前数据一致性。
- **本地数据层:** DuckDB + Parquet，按 raw/silver/gold/models/reports/logs 分层。
- **球员评分:** 基于球队积分代理目标的 PyTorch 研究候选，具备 holdout 指标、availability/quality cap、模型运行登记和本地准入生命周期。当前只属部分交付：active rating 早于当前特征矩阵，本地没有可复核模型运行，也没有合格的独立监督标签；不能写成已验证的球员能力真值。
- **真实标签契约:** `player_truth_labels.parquet` schema、来源政策、校验和手动快照导入。当前文件行数和来源分布必须在锁定运行时内容级验证；标签独立性和时间切分仍是模型准入门槛。
- **神经网络候选模型:** `scoutfootball train-rating-nn` 使用 `rating_feature_matrix.parquet` + `player_truth_labels.parquet` 训练监督式 sklearn MLP 候选模型，并写入 `data/models/player_rating_nn/`；除非同切分下优于当前优化器和 baseline，否则不替换 `player_ratings_optimized.parquet`。
- **评分模型卡:** `MODEL_CARD.md` 记录数据源、标签定义、适用边界和已知偏差。
- **比分预测:** Independent Poisson baseline，含比分概率矩阵。
- **产品与可视化:** 15 页 Streamlit 工作台；Liquid Glass 静态工作台当前有 24 个顶层视图目标，覆盖核心分析、世界杯、战术、质量和治理。这个数量不代表所有流程都已成熟，准确边界以 `CAPABILITIES.md` 为准。球探工程、决策包、战术工程和部分简报联动默认保存在浏览器本地，不是云同步或多人协作；预计阵容和赛事模型结果也不是官方实时球队新闻。

## Liquid Glass 前端

`frontend/` 目录包含静态分析工作台，采用统一的几何图标系统（无 emoji）。所有导航图标使用最小化 Unicode 符号（◎ ◇ € △ □ ⌁ ▣ ⬡ ⊕ ⟷ ⊞），保持视觉一致性。API、本地 Parquet 派生 JSON、demo 字符串和导入的战术板工程字段进入 HTML 前都会转义或清洗。

**核心分析工作流视图（节选，不是完整导航清单）：**

| 视图 | 说明 | 数据来源 |
| --- | --- | --- |
| **总览** (◎) | 产物注册表、数据健康、覆盖指标 | `/artifacts` API |
| **球员** (◇) | 球员池、雷达图、位置内百分位 | `/ratings`、`/players/{name}` API |
| **身价** (€) | 身价偏离散点图、高估/低估排名 | `/value-summary` API |
| **预测** (△) | 比赛预测、比分概率矩阵、交锋记录与近期状态 | `/predictions/{home}/{away}`、`/predictions/{home}/{away}/h2h` API |
| **球探** (□) | 复核筛选、本地状态/备注、版本化工作区导入导出、可选的冲突安全本地 API 持久化 | `/review-queue`、`/watchlist`、`/shortlist`、`/scouting-workspaces/*` |
| **动作价值** (⌁) | xT/VAEP 排名、样本筛选、3 场样本的球员→比赛动作证据、战术板热区联动 | `/action-values`、`/action-values/evidence/{player_id}` API |
| **报告** (▣) | 模型运行记录、后端契约、指标 | `/reports/model-runs` API |

**世界杯入口视图（节选；当前还包括淘汰赛和赛事中心）：**

| 视图 | 说明 |
| --- | --- |
| **赛程** (⬡) | 小组赛赛程、分组、场馆 |
| **名单** (⊕) | 球队阵容含俱乐部、联赛、评分、置信度 |
| **对比** (⟷) | 两队实力对比含雷达叠加 |
| **出线** (⊞) | 小组出线概率、48 队实力排名 |

## Demo 数据

当 FastAPI 后端不可用时，有映射的视图会回退到 `frontend/data/` 的跟踪静态快照。静态快照是缓存数据，不是实时数据；特定估算数据仍会显示 **DEMO** 标记。

查看真实数据：

```bash
# FastAPI 在同一 origin 提供前端和本地 Parquet/DuckDB 产物
PYTHONPATH=src uv run python -m scoutfootball serve --host 127.0.0.1 --port 8000

# 浏览器打开 http://127.0.0.1:8000
```

`frontend/config.js` 默认使用 same-origin API。单独启动纯静态服务器只适合验证 STATIC 回退；除非显式修改配置，它不会调用另一个端口上的 API。

生成前端读取的评分产物：

```bash
uv sync
PYTHONPATH=src uv run python -m scoutfootball ingest
PYTHONPATH=src uv run python -m scoutfootball build-features
PYTHONPATH=src uv run python -m scoutfootball train

# 可选监督式 NN 候选；player_truth_labels 行数不足时会跳过
PYTHONPATH=src uv run python -m scoutfootball train-rating-nn
```

球探决策默认只保存在浏览器。需要同机后端持久化时显式启用：

```powershell
$env:SCOUTFOOTBALL_ENABLE_WORKSPACE_WRITES="1"
uv run python -m scoutfootball serve --host 127.0.0.1 --port 8000
```

更新使用 `If-Match` 服务器 revision 防止静默覆盖，写入采用原子替换并保留上一版备份。默认拒绝非回环地址访问；`SCOUTFOOTBALL_ALLOW_REMOTE_WORKSPACE_WRITES=1` 只应在受信网络和明确理解风险后启用。该能力不是云同步或多人协作。

## 世界杯准备度

| 功能 | 状态 |
| --- | --- |
| 48 队阵容评分覆盖 | 进行中 — 当前覆盖五大联赛，世界杯阵容需补充更多联赛数据 |
| 比赛预测 (Independent Poisson) | 基线可用 |
| 球员雷达 / Pizza chart | 已集成 mplsoccer |
| 位置内排名 | 可用，带置信度标记 |
| 比分概率矩阵 | Streamlit 可用 |
| 电子战术板 | 本地画布、动画、PNG/PDF/WebM/GIF、可选 MP4、报告快照和 schema 迁移已实现 |
| Dixon-Coles + 时间衰减 | 已实现基线与校准指标 |

## 当前已知限制

**评分系统：**
- 2026-07-16 审计只能读取真值标签 footer/schema，无法解码内容和 `label_source` 分布；在锁定运行时完成内容级来源政策审计前，来源构成和监督资格均为未核验，不能用 footer 行数证明球员级验证
- 评分系统处于校准阶段；强队（Barcelona、Real Madrid）可能被系统性低估
- 联赛截距偏差存在（Serie A -16.6、Ligue 1 -11.3）

**数据覆盖：**
- 动作价值聚合文件的本地 footer 在 2026-07-16 审计中报告 9,951 行，但当前运行时未能完整解码，不能视为数据已可用；比赛证据下钻仅含 3 场比赛的 94 条球员—比赛证据记录，不是 tracking 或 94 条事件，二者都不是全量联赛覆盖
- FBref 数据限于 5 赛季；粗位置映射需要 StatsBomb/阵型数据
- 世界杯阵容视图已填充预计/记录数据，但正式名单、预计征召和评分覆盖必须分开；五大联赛外覆盖仍不完整

**前端：**
- API 不可用时，有映射的视图回退到跟踪静态快照；静态快照不是实时数据
- API 状态 pill 显示 LIVE（API 在线）、STATIC（回退到快照）或 OFFLINE（均不可用）
- review queue 已分页，每页 50 条，避免一次渲染大量卡片
- 球探复核状态和备注默认只保存在浏览器；已有版本化导入导出和显式开启的同机持久化，但尚不是云端多人审计 workspace
- 部分 VAEP 行只有 `player_id`，身份映射尚未完成
- 战术板 MP4 导出需要系统安装 ffmpeg

**范围边界：**
- 空间/视频分析（StatsBomb 360、tracking 数据）仍是依赖门槛约束的本地研究，不是当前能力
- 公开链接、云同步、组织账号和战术板实时协作不在当前项目章程范围内
- 移动端战术板编辑属于可选方向，必须先证明收益不会增加单人维护复杂度

## 电子战术板

电子战术板已作为 `frontend/` 内的本地优先教练和分析工作台落地，参考 [Tactico](https://tactico.pro/)、[DrawTactics](https://drawtactics.com/animated-tactics-board)、[TacticSlate](https://tacticslate.com/football-tactic-board) 和 [Metrica Tactical Boards](https://www.metrica-sports.com/help-center/tactical-boards) 等案例。当前能力包括标准化球场坐标、阵型与定位球、绘图工具、逐帧/路径动画、本地 JSON 工程、schema 迁移、报告快照和 PNG/PDF/WebM/GIF 导出。MP4 是需要 ffmpeg 的可选本地后端能力。公开链接、云同步、组织账号和实时协作在当前章程下属于非目标；本地视频叠画和 tracking 导入仍是有前置门槛的研究方向。

中长期开发顺序和工程准入门槛见 [`ROADMAP.md`](ROADMAP.md)，当前工作只从 [`TASKS.md`](TASKS.md) 顶部选择；旧 P1.5 编号仅属历史记录。

## 桌面应用

仓库包含 Electron/PyInstaller 打包配置和历史 macOS arm64 构建记录。本次审计没有重新验证 `.dmg`、签名、安装、自动更新或 release 资产，因此桌面交付仍是部分核验，不能写成当前可下载承诺。

| 功能 | 状态 |
|---|---|
| macOS arm64 (.dmg) | 历史构建记录；当前资产/签名/安装未核验 |
| GitHub Release 自动更新 | 代码路径存在；本轮未端到端核验 |
| 系统托盘 | 代码路径存在 |
| 内置数据 | 打包配置存在；当前实际内容需检查 release 资产 |
| Windows 构建 | 脚本存在；当前资产/安装未核验 |

从源码构建：

```bash
cd desktop && npm install
bash scripts/build-desktop.sh --mac
```

预期本地产物目录：`desktop/dist/`；具体版本化文件名以构建配置为准。

## 本地数据概览

README 不再维护易漂移的缓存行数，当前状态以生成的数据健康报告和 [`CAPABILITIES.md`](CAPABILITIES.md) 为准。2026-07-16 审计中，若干 Parquet footer 可读但完整解码失败，footer 行数不能证明数据可用。StatsBomb 比赛索引、3 场事件样本和球员—比赛证据是不同文件与粒度，不能合并成一个覆盖数字。

## 顶层架构

目标结构是 ScoutFootball Core（来源/许可、快照/lineage、身份、数据契约、模型治理、证据包、工作区、适配器）加 World Cup、Recruitment、Opposition & Match 和后续 Academy 场景包。有门槛的阶段、依赖和非目标只在 [`ROADMAP.md`](ROADMAP.md) 维护。

## 快速开始

**前置条件：** Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)（快速 Python 包管理器）。

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆并安装
git clone https://github.com/Mentat-Uran/ScoutFootball_for_World_Cup.git
cd ScoutFootball_for_World_Cup
uv sync

# 分步验证与构建：
PYTHONPATH=src uv run python -m scoutfootball info      # 项目信息
PYTHONPATH=src uv run python -m scoutfootball validate   # 数据验证
PYTHONPATH=src uv run python -m scoutfootball ingest     # 数据采集
PYTHONPATH=src uv run python -m scoutfootball build-features
PYTHONPATH=src uv run python -m scoutfootball train      # 训练评分

# 启动同源 Web 界面与 API
PYTHONPATH=src uv run python -m scoutfootball serve --host 127.0.0.1 --port 8000
```

浏览器打开 http://127.0.0.1:8000 查看 Liquid Glass 前端，或运行 Streamlit：

```bash
uv run streamlit run src/scoutfootball/app/streamlit_app.py
```

**首次运行提示：** 部分采集路径会下载并缓存公开数据，需要网络连接；另一些路径需要手动/授权的本地输入。`scripts/demo.sh` 已与同源 FastAPI 设置对齐（端口 8000）并含 `--smoke` 健康检查，是本地 demo 流水的标准启动入口。

## 技术栈与合规

- **技术栈:** Python, uv, DuckDB + Parquet, pandas, scikit-learn, Streamlit, Plotly, mplsoccer, FastAPI, PyTorch.
- **合规准则:**
  - 不绕验证码，不恶意高频爬取。
  - 商用数据源（如 Transfermarkt）仅支持手动或授权导入。
  - 公开 StatsBomb Open Data 衍生产物必须标明数据来源。

---
*ScoutFootball — Local-First Football Analytics & Player Research*
