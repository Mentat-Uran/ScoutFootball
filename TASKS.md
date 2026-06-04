# 任务路线图

当前状态：**Phase 1-8 已完成，评分系统优化中。**

## ✅ 已完成

**数据源 (5 个，覆盖 10 赛季):**
- FBref: 14,356 条, 5联赛, 5赛季 (2021-2026), 含 misc + shooting
- Football-Data.co.uk: 17,936 场, 5联赛, 10赛季 (2016-2026)
- Understat: 27,254 条, 5联赛, 10赛季 (2016-2026), 含 xG/xA/npxG
- StatsBomb Open Data: 126 场比赛, 11,871 事件, 94 场逐场球员数据
- Club Elo: 630 支球队 Elo 评级

**特征工程:**
- 团队级: team_match (17,814行), team_rolling
- 球员级: player_match (14,450行), player_rolling
- 特征族: 出勤、进攻、防守、控球、质量、趋势、经验

**模型:**
- 独立 Poisson 比分预测 (按球队名模糊匹配)
- value_fairness OOF (6,513行, MAE €4.28M vs baseline €4.45M)
- 评分优化器: PyTorch GPU, 77 参数, Holdout Spearman=0.8382

**工程:**
- Pipeline 端到端: ingest → build-features → train
- API match prediction 按球队名预测
- demo fallback 收紧 (log.warning + 三级状态标记)
- 测试套件: 71 个测试通过

**GPU 远程计算:**
- Windows RTX 5070 Ti REST 服务器 (192.168.0.189:8420)
- Mac 客户端通过 REST API 发送优化任务
- 异步任务模式，支持 holdout split 评估

## ⏳ 待完成

**评分系统平衡 (优先):**
- [ ] 联赛系数优化: 当前 EPL 占比过高，需平衡各联赛权重
- [ ] 位置权重调整: 前锋 attack 权重过高，需降低 ST/W 的攻击权重
- [ ] 出场时间惩罚微调: 400分钟底分0.4，1200分钟满分
- [ ] 参考: scripts/RATING_IMPROVEMENT_PROMPT.md

**数据扩展:**
- [ ] FBref 更多赛季 (2016-2021 被 CAPTCHA 封禁，需手动导入)
- [ ] StatsBomb 逐场数据扩展 (当前仅 126 场)
- [ ] Transfermarkt 手动导入 (当前用合成 market_value 占位)

**模型扩展:**
- [ ] Dixon-Coles 模型
- [ ] 更多特征: 传球、控球详细统计

**应用:**
- [ ] Streamlit MVP 集成优化后评分
- [ ] FastAPI 服务层

## 全局验收原则

- 数据处理必须可复现、可缓存、可校验、可回溯
- ETL 必须幂等
- 时间序列任务不能泄露未来信息
- 模型必须有简单合理的基线对照
- Transfermarkt 只允许手动导入
- FBref 只作为受限补充源
