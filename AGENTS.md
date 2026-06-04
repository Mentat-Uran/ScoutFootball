# AGENTS.md

你是一个务实的 AI 开发助手。回答和开发都要直接、准确、可验证，不铺垫，不夸张，不把未完成内容说成已完成。

## 项目真源

开始任何开发前先阅读：

1. `deep-research-report.md`：架构、数据源、模型路线和合规依据。
2. `TASKS.md`：当前 roadmap 真源。
3. `README.md`：项目定位、默认技术栈和使用说明。

如果三者冲突，优先级为：

1. 合规与数据权利约束。
2. `TASKS.md` 的当前阶段和验收标准。
3. `deep-research-report.md` 的架构分析。
4. `README.md` 的对外说明。

## 当前项目状态

Pipeline 端到端可运行：`scoutlab ingest` → `scoutlab build-features` → `scoutlab train`。

**数据源 (5 个，覆盖 10 赛季):**
- FBref: 14,356 条, 5联赛, 5赛季 (2021-2026)
- Football-Data.co.uk: 17,936 场, 5联赛, 10赛季 (2016-2026)
- Understat: 27,254 条, 5联赛, 10赛季 (2016-2026), 含 xG/xA/npxG
- StatsBomb Open Data: 126 场比赛, 11,871 事件
- Club Elo: 630 支球队 Elo 评级

**评分系统:**
- PyTorch GPU 优化器, 77 参数, Holdout Spearman=0.8382
- 联赛系数: 基于 UEFA 官方国家系数 (football-coefficient.eu)
- 出场时间惩罚: 硬阈值 + 线性衰减 (400分钟底分, 1200分钟满分)
- 位置缩放: 前锋 attack 权重降低 (ST ×0.85, W ×0.90)
- 待优化: 联赛系数和位置惩罚的平衡 (见 scripts/RATING_IMPROVEMENT_PROMPT.md)

**GPU 远程计算:**
- 服务器: Windows RTX 5070 Ti (192.168.0.189:8420)
- 客户端: Mac 通过 REST API 发送优化任务
- 脚本: `scripts/gpu_server.py`, `scripts/gpu_client.py`

**其他已完成:**
- Pipeline 全接通 (ingest/build-features/train)
- value_fairness OOF 训练 (合成 market_value 占位)
- Poisson 比分预测 (按球队名模糊匹配)
- StatsBomb 逐场球员数据聚合 (94 场)
- demo fallback 收紧 (log.warning + 三级状态标记)

**待完成:**
- 评分系统平衡优化 (联赛系数、位置权重)
- Transfermarkt 真实数据导入
- Streamlit MVP 集成优化后评分
- Dixon-Coles 模型扩展
- FBref 更多赛季 (2016-2021 被 CAPTCHA 封禁)

除非用户明确要求进入实现阶段，否则不要补完整业务代码，也不要越过 `TASKS.md` 当前阶段批量补齐后续业务模块。

## 技术默认值

- 语言：Python
- 包管理器：`uv`
- 本地数据层：DuckDB + Parquet
- schema 与参数校验：Pydantic
- 测试：pytest
- 代码质量：Ruff
- MVP 可视化：Streamlit + Plotly
- 后续服务层：FastAPI
- 后续生产存储：PostgreSQL

## GPU 优化

评分权重优化使用 PyTorch，支持 Mac MPS 和 Windows CUDA。重型计算优先在 Windows 5070 Ti 上运行。

GPU 远程计算服务器:
- 服务器: Windows RTX 5070 Ti (192.168.0.189:8420)
- 客户端: Mac 通过 REST API 发送优化任务
- 优化结果: Holdout Spearman 0.8382, 过拟合 gap 0.03

## 开发原则

- 按 `TASKS.md` 从前到后推进，不跳阶段
- 每次实现一个小而稳定的切片
- 优先实现可测试的纯函数和清晰 I/O
- 数据处理必须可复现、可缓存、可校验、可回溯
- ETL 必须幂等
- 不把任何外部源 ID 直接当内部主键
- 不把"球员水平"做成不可解释的单一分数

## 数据源与合规边界

**允许:**
- StatsBomb Open Data (官方公开 JSON)
- Football-Data.co.uk (官方 CSV)
- Club Elo (官方 API/CSV)

**谨慎:**
- Understat: 赛季格式标准化 ("201617" → "1617"), 缺失指标填 0 后重算
- FBref: 限速缓存, 德甲回退, 2020 前被 CAPTCHA 封禁

**禁止:**
- Transfermarkt 自动抓取
- 绕过验证码/反爬
- 高频请求受限网站

## 测试要求

- 单元测试不能访问真实网络
- 模型测试必须包含简单基线
- 概率模型必须验证概率和/Brier/log loss/RPS
