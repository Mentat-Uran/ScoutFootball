# 任务路线图

当前状态：**评分系统优化迭代中。**

## ✅ 已完成

- 5 数据源接入 (FBref, Football-Data, Understat, StatsBomb, Club Elo)
- 10 赛季数据覆盖 (2016-2026), 27,254 球员
- Pipeline 端到端: ingest → build-features → train
- PyTorch GPU 评分优化器 (77 参数)
- GPU 远程计算服务器 (Windows RTX 5070 Ti REST API)
- Poisson 比分预测, value_fairness OOF
- 联赛系数窄幂曲线校准 (UEFA 系数)
- 出场时间惩罚 (400分钟底分0.42, 1200分钟满分)
- attack 维度位置缩放 (ST×0.94, W×0.93, AM×0.97)

## ⏳ 当前问题 (优先修复)

**评分系统位置权重失衡:**
- [ ] CM 的 quality 权重过高 (0.54)，导致 Top 30 中 CM 占 28 人
- [ ] ST 的 attack 权重过低 (0.086)，前锋被过度压低
- [ ] 优化器在新约束下过拟合
- [ ] 目标: Top 30 中 ST 6-10人, W 4-6人, CM 8-12人

**可能的解决方案:**
1. 给 quality 维度加位置缩放 (CM quality ×0.9)
2. 限制 ST 的 attack 最低权重 (下限 0.15)
3. 在优化 loss 中加位置多样性惩罚
4. 分开训练: 先固定联赛系数，再优化位置权重

## 后续待完成

- FBref 更多赛季 (2016-2021 被 CAPTCHA 封禁)
- Transfermarkt 手动导入
- Streamlit MVP
- Dixon-Coles 模型
