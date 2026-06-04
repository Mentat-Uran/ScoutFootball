# AGENTS.md

你是一个务实的 AI 开发助手。回答和开发都要直接、准确、可验证。

## 当前项目状态

Pipeline 端到端可运行：`scoutlab ingest` → `scoutlab build-features` → `scoutlab train`。

**数据源 (5 个，覆盖 10 赛季):**
- FBref: 14,356 条, 5联赛, 5赛季 (2021-2026)
- Football-Data.co.uk: 17,936 场, 10赛季 (2016-2026)
- Understat: 27,254 条, 10赛季 (2016-2026), 含 xG/xA/npxG
- StatsBomb: 126 场, Club Elo: 630 队

**评分系统 (当前迭代中):**
- PyTorch GPU 优化器, 77 参数
- 最新优化结果: Holdout Spearman=0.7952, 过拟合 gap=0.037
- 联赛分布: EPL 11, Bundesliga 8, La Liga 5, Serie A 3, Ligue 1 3 (平衡)
- 位置分布: CM 28, ST 2 (CM 过度集中，需修复)
- GPU 远程计算: Windows RTX 5070 Ti (192.168.0.189:8420)

**当前问题:**
- CM 的 quality 权重过高 (0.54)，导致 CM 球员霸榜
- ST 的 attack 权重过低 (0.086)，前锋被过度压低
- 优化器在新约束下过拟合

**待完成:**
- 评分系统位置权重平衡
- Transfermarkt 真实数据导入
- Streamlit MVP
- Dixon-Coles 模型

## 技术默认值

Python, uv, DuckDB+Parquet, PyTorch, Streamlit, pytest, Ruff

## 开发原则

- 数据处理可复现、可缓存、可校验
- ETL 幂等
- 模型必须有基线对照
- Transfermarkt 只允许手动导入
- FBref 只作为受限补充源
