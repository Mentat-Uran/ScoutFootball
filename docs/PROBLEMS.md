# 评分系统当前问题记录

> 2026-06-05 优化器修复后的评估结果

## 2026-06-10 前端安全边界修复

### 已直接处理

1. **本地/API 字符串直接进入 `innerHTML`**：`frontend/app.js` 新增 `escapeHtml()`、`escapeAttr()` 和 `sanitizeCssPercent()`，球员、球队、报告、球探队列、动作价值、世界杯样例和战术板工程列表等渲染点已统一转义。
2. **CSV 导出公式注入风险**：球员 CSV 导出新增 `csvCell()`，对 `= + - @ tab CR` 开头的单元格加前缀并按 CSV 规则转义引号。
3. **战术板 JSON 导入边界不足**：`frontend/tactical-board.js` 新增 `sanitizeProject()`，限制导入大小、对象数、帧数、文本长度、坐标范围、颜色/样式字段和对象类型；localStorage 读取、保存和导入都先走 sanitizer。

## 2026-06-23 球探与动作价值恢复后的已知边界

### 已修复

1. **两项导航被临时隐藏**：球探和动作价值入口已恢复。
2. **球探 payload 字段错配**：前端已从 `player_name` 读取姓名，并保留 reason/status/note/date/snapshot 字段。
3. **动作价值 payload 字段错配与运行时异常**：现行主字段改为 `xt_per_90`/`vaep_per_90`，移除未定义 `actionData` 引用。
4. **纯静态启动无数据**：有静态映射的 API 路径在 404 时继续回退 `frontend/data/`。
5. **BUG-001：静态快照包含 repr 字符串**：`scripts/export_static_frontend_data.py` 之前对 dataclass/Pydantic response 使用 `str(obj)` fallback，导致 `frontend/data/health.json` 和 `frontend/data/players_list.json` 包含 Python repr 字符串而非合法 JSON dict。已修复：dataclass/Pydantic response 必须经过 JSON-safe serializer（`dataclasses.asdict()` 或 `model.model_dump()`），遇到不可序列化对象时报错终止而非静默写入 repr。验证：静态 JSON 契约测试覆盖 `frontend/data/` 下各文件。

### 仍未解决，必须保留

1. **球探状态不是正式审计记录**：复核状态、备注和手动选择仍保存在 localStorage；清理浏览器数据会丢失，也不能跨设备同步。正式回灌前必须建立版本化 workspace、导入校验和来源字段。
2. **VAEP 身份映射不完整**：部分产物只有 `player_id`，前端只能显示 ID。完成稳定实体映射前，不应把这些行与姓名级球探结论自动合并。
3. **动作价值不是全量联赛能力**：15,062 行只代表当前 StatsBomb Open Data 产物。任何公开结论必须显示样本量、分钟门槛、覆盖范围和 StatsBomb attribution。
4. **完整浏览器 CI 未完成**：当前仅有 Node 语法检查和单元测试，无 Selenium/Playwright 端到端测试覆盖。



## 修复内容

1. **Pearson=0.0 bug** — `gpu_server.py` 中用 `spearmanr()` 第二返回值当 Pearson，实际是 p-value。已改用 `evaluate_params()` 中的 `pearsonr()`。
2. **无 holdout 验证** — 旧版 `/optimize` 用全量数据优化+评估，本质是训练集表现。已添加 `test_seasons`/`min_train_seasons` 参数，优化只在训练集，评估在 holdout 测试集。
3. **ST quality=0.94 霸榜** — ST/W 的 `POSITION_DIMENSION_CAPS` 中 quality 未封顶，attack 被 cap 压死后 quality 绕路接管。已添加 ST quality cap=0.30, W quality cap=0.28；移除 ST attack_scale 压缩。

## 修复后指标

| 指标 | 修复前 (全量, Pearson bug) | 修复后 (holdout) |
|------|---------------------------|------------------|
| Spearman | 0.7393 (全量, 过拟合) | 0.6788 (holdout) |
| Pearson | 0.0 (bug) | 0.6899 |
| ST quality 权重 | 0.94 (霸榜) | 0.05 (cap 生效) |
| ST attack 权重 | 0.03 (被压死) | 0.92 (前锋回归进攻主导) |
| 过拟合检查 | 无 | overfit_gap=0.0678 |

Holdout 分割: train=9赛季 (1617-2425), test=2526赛季。

## 2526赛季五大联赛前四预测问题

### Premier League
| 预测排名 | 球队 | 预测评分 | 实际积分 | 问题 |
|---------|------|---------|---------|------|
| 1 | Everton | 69.43 | 49 | **严重高估** — 出勤驱动虚高 |
| 2 | Manchester City | 68.36 | N/A | 数据不完整 |
| 3 | Arsenal | 67.60 | 85 | **排名偏低** — 实际冠军 |
| 4 | Liverpool | 66.72 | 60 | 排名合理 |

### La Liga
| 预测排名 | 球队 | 预测评分 | 实际积分 | 问题 |
|---------|------|---------|---------|------|
| 1 | Barcelona | 65.65 | 94 | 排名正确 |
| 2 | Villarreal | 61.75 | 72 | 排名合理 |
| 3 | Real Madrid | 61.34 | 86 | **排名偏低** — 实际积分最高 |
| 4 | Real Betis | 58.95 | N/A | 数据不完整 |

### Bundesliga
| 预测排名 | 球队 | 预测评分 | 实际积分 | 问题 |
|---------|------|---------|---------|------|
| 1 | Bayern Munich | 66.66 | 89 | 排名正确 |
| 2 | Stuttgart | 66.16 | 62 | **高估** — 出勤驱动 |
| 3 | Hoffenheim | 65.37 | 61 | **高估** — 出勤驱动 |
| 4 | Dortmund | 62.08 | 73 | 排名偏低 |
| 5 | Leverkusen | 61.22 | 59 | 实际排名更高 |

### Serie A
| 预测排名 | 球队 | 预测评分 | 实际积分 | 问题 |
|---------|------|---------|---------|------|
| 1 | Inter | 64.48 | 87 | 排名正确 |
| 2 | Roma | 63.42 | 73 | 排名合理 |
| 3 | Como | 61.05 | 71 | 排名偏高 |
| 4 | Milan | 59.98 | 70 | 排名合理 |
| 7 | Napoli | 55.45 | 76 | **严重低估** — 实际第2 |

### Ligue 1
| 预测排名 | 球队 | 预测评分 | 实际积分 | 问题 |
|---------|------|---------|---------|------|
| 1 | Rennes | 61.57 | 59 | **不应排第1** |
| 2 | PSG | 60.05 | N/A | 应排第1 |
| 3 | Lens | 58.44 | 70 | 排名偏低 |

总体相关性: Spearman=0.56, Pearson=0.55, N=722

## 核心问题分析

### 1. 出勤驱动虚高 (最严重)

Everton、Stuttgart、Hoffenheim、Rennes 等中游队排名虚高，因为这些队有高出场分钟的中场/后卫。availability 维度在 CM/FB/CB/GK 的权重仍偏高（0.30-0.36），球队平均评分被出勤多的球员拉高。

**根因**: 球队积分与球员出勤高度相关，优化器通过出勤捷径提升 Spearman。即使加了 cap，availability 在后场位置仍占最大权重。

**可能方案**:
- 降低 availability 在所有位置的 cap（当前 CM=0.30, CB=0.36, GK=0.32）
- 在球队聚合时用评分中位数而非分钟加权均值
- 引入非出勤依赖的训练目标（如球员个体排名标签）

### 2. 强队核心球员被低估

Napoli、Real Madrid、Arsenal 等强队的顶级球员排名偏低。可能原因：
- 2526 赛季数据不完整（部分球队积分 N/A）
- 强队球员轮换多，单赛季出场分钟相对少
- 联赛强度曲线对强联赛内部差异压缩过度

### 3. 训练目标局限

当前唯一训练目标是球队积分 Spearman/Pearson 相关性。这导致：
- 优化器倾向出勤捷径（出勤多→球队积分高→相关性高）
- 无法区分"好球员在烂队"vs"普通球员在强队"
- 缺少球员个体层面的监督信号

**需要**: 真实影响力标签（身价、奖项、专家排名）或事件动作价值（xT/VAEP）作为额外监督。

### 4. 数据不完整

2526 赛季部分球队在 Football-Data 中无积分数据（显示 N/A），影响评估准确性。FBref 只有 3 赛季数据，Understat 补充了 5 个更早赛季但缺少防守/控球指标。

## 下一步优先级

1. **降低 availability cap** — CM/FB/CB/GK 的 availability cap 从 0.30-0.36 降到 0.20-0.25
2. **球队聚合改用中位数** — 减少出勤多但评分一般的球员对球队评分的拉拽
3. **引入球员个体标签** — Transfermarkt 身价或专家排名作为辅助监督
4. **补全 2526 赛季数据** — 确保 Football-Data 覆盖完整赛季

## 2026-06-05 本轮处理记录

### 已直接处理

1. **availability cap 继续下调**：`scripts/optimize_ratings_gpu.py` 中所有位置的 availability 上限已收敛到 0.18-0.20，CM/CB/GK 不再允许 0.30-0.36 的出勤权重。
2. **球队聚合去 raw minutes 化**：球队赛季评分从纯分钟加权均值改为 capped minutes + core rotation 稳健聚合，避免评分层和球队层重复奖励原始出勤。
3. **评估覆盖率显式输出**：`evaluate_params()` 新增 team coverage，CLI 和远程 API 都能报告 target/rated/matched teams 和 coverage。
4. **2526 五大联赛测试集队名修补**：从 Football-Data 2025/2026 CSV 重新读取 E0/SP1/D1/I1/F1，并把本地测试集中的 Football-Data 简称直接替换为评分侧队名。

本轮直接编辑的测试集队名映射：

| Football-Data | ScoutFootball |
| --- | --- |
| Leeds | Leeds United |
| Man City | Manchester City |
| Man United | Manchester Utd |
| Newcastle | Newcastle United |
| Nott'm Forest | Nottingham Forest |
| Tottenham | Tottenham Hotspur |
| West Ham | West Ham United |
| Alaves | Alavés |
| Ath Bilbao | Athletic Club |
| Ath Madrid | Atlético Madrid |
| Betis | Real Betis |
| Celta | Celta Vigo |
| Espanol | Espanyol |
| Sociedad | Real Sociedad |
| Vallecano | Rayo Vallecano |
| Ein Frankfurt | Eintracht Frankfurt |
| FC Koln | Köln |
| Hamburg | Hamburger SV |
| M'gladbach | Gladbach |
| Mainz | Mainz 05 |
| Verona | Hellas Verona |
| Paris SG | Paris Saint-Germain |

备份文件：

- `data/raw/football_data/combined_results.parquet.bak-20260605044151`
- `data/raw/football_data/2526/E0.csv.bak-20260605044151`
- `data/raw/football_data/2526/SP1.csv.bak-20260605044151`
- `data/raw/football_data/2526/D1.csv.bak-20260605044151`
- `data/raw/football_data/2526/I1.csv.bak-20260605044151`
- `data/raw/football_data/2526/F1.csv.bak-20260605044151`

### 本机小规模测试结果

未使用 5070 Ti 服务器。命令：

```bash
PYTHONPATH=src uv run python scripts/optimize_ratings_gpu.py --data_dir /tmp/scoutfootball-smoke-patched.zKc8Cq --pop 2 --steps 20 --cv-folds 0 --stability-runs 0 --importance-repeats 0 --patience 10
```

修补后 2526 五大联赛 coverage：

| 联赛 | matched/target | coverage |
| --- | ---: | ---: |
| Premier League | 20/20 | 1.00 |
| La Liga | 20/20 | 1.00 |
| Bundesliga | 18/18 | 1.00 |
| Serie A | 20/20 | 1.00 |
| Ligue 1 | 18/18 | 1.00 |

小规模 smoke test 指标：

| 指标 | 修补后小规模结果 |
| --- | ---: |
| Holdout N | 96 |
| Holdout Spearman | 0.5729 |
| Holdout Pearson | 0.5815 |
| overfit gap | +0.0166 |

### 仍未解决，必须保留

1. **球员真实影响力标签仍不充分**：player_truth_labels.parquet 当前有 41,389 行（Transfermarkt 身价 33,532 + expert_tier 7,840 + award 17），但训练目标仍主要来自球队积分，无法可靠区分"强队普通球员"和"弱队好球员"。
2. **Top 20 仍偏 CM/后场**：本机小规模测试 Top 20 仍包含较多 CM/CB/FB，例如 Declan Rice、Mathias Jensen、Bruno Guimarães、Luke Ayling、Kiernan Dewsbury-Hall、James Garner 等。说明出勤/中后场代理信号仍会影响榜单。
3. **强队核心低估仍需复盘**：Arsenal、Real Madrid、Napoli、PSG 等问题不能因为 coverage 修好就视为解决；需要完整优化、误差案例表和球员级真值标签共同判断。
4. **直接编辑测试集只是临时修补**：本轮修的是 2526 五大联赛 team-name alias，不是长期的数据标准化方案。后续应把这类映射纳入统一 entity normalization，而不是长期手改 raw/test 文件。
5. **本机 smoke test 不是正式模型结论**：`--pop 2 --steps 20` 只验证代码路径和数据覆盖，不能替代完整优化、CV、稳定性、feature importance 和人工误差审查。

---

## GPU 重跑复盘（2026-06-05）

### 运行配置

- 设备：NVIDIA GeForce RTX 5070 Ti (CUDA)
- 参数：pop=32, steps=500, lr=0.05, patience=80
- 组合目标权重：Spearman=0.50, NDCG@20=0.20, 位置内一致性=0.15, 极端惩罚=0.10, 先验=0.05
- 训练赛季：1617-2425（9赛季），测试赛季：2526

### 指标对比

| 指标 | Baseline | 优化后 | 变化 |
|------|----------|--------|------|
| Holdout Spearman | 0.4250 | 0.6346 | +0.2096 |
| Holdout Pearson | 0.4068 | 0.6251 | +0.2184 |
| Overfit gap | — | +0.0537 | — |

### 各联赛 2526 Holdout

| 联赛 | Spearman | Pearson | N | Coverage |
|------|----------|---------|---|----------|
| Serie A | 0.831 | 0.891 | 19 | 0.95 |
| Bundesliga | 0.735 | 0.710 | 13 | 0.72 |
| La Liga | 0.730 | 0.810 | 12 | 0.60 |
| Ligue 1 | 0.725 | 0.635 | 17 | 0.94 |
| Premier League | 0.325 | 0.526 | 13 | 0.65 |

### 位置权重（优化后 capped）

| 位置 | availability | attack | defense | possession | quality |
|------|-------------|--------|---------|------------|---------|
| ST | 0.0450 | 0.7350 | 0.0277 | 0.0435 | 0.1488 |
| W | 0.0378 | 0.7508 | 0.0266 | 0.0489 | 0.1360 |
| AM | 0.0722 | 0.3459 | 0.0536 | 0.2515 | 0.2769 |
| CM | 0.1800 | 0.2200 | 0.1122 | 0.2478 | 0.2400 |
| DM | 0.1395 | 0.0794 | 0.2981 | 0.2810 | 0.2020 |
| FB | 0.2000 | 0.1600 | 0.1173 | 0.2437 | 0.2790 |
| CB | 0.1800 | 0.1000 | 0.2298 | 0.2402 | 0.2500 |
| GK | 0.1800 | 0.0598 | 0.2956 | 0.1845 | 0.2800 |

### 误差案例分析

**Premier League（Spearman=0.325，coverage=0.65）**：
- Coverage 0.65 意味着 20 支球队只匹配了 13 支，统计不稳定。
- 7 支未匹配球队的评分缺失导致排名偏差。
- 低 coverage 可能因为 2526 赛季 PL 球队名 alias 不完整或部分球队评分数据缺失。
- **结论**：PL 的 0.325 Spearman 不能作为模型在 PL 上真实表现的可靠指标，需补全 alias 和 coverage 后重新评估。

**La Liga（Spearman=0.730，coverage=0.60）**：
- Coverage 0.60 更低，12/20 支球队匹配。
- 但 Spearman 仍有 0.730，说明匹配的球队排序基本正确。
- **结论**：coverage 不足是主要问题，不是模型排序能力问题。

**Serie A / Ligue 1（coverage ≥ 0.94）**：
- 高 coverage 下 Spearman 分别为 0.831 和 0.725，模型排序能力可靠。
- **结论**：这两个联赛的评分结果可以作为中等置信度参考。

### 出勤捷径改善

- ST/W 的 availability 权重从之前的 0.10+ 降到 0.045/0.038，出勤对前锋/边锋评分的影响大幅削弱。
- CM/FB/CB/GK 的 availability 仍在 0.18-0.20（cap 生效），但 attack/defense/possession/quality 权重分布更合理。
- 组合目标中的极端惩罚（0.10 权重）对出勤捷径产生了额外压制。

### 仍需解决的问题

1. **Premier League 和 La Liga coverage 不足**：需补全 2526 赛季队名 alias 或增加评分侧球队覆盖。
2. **强队核心低估**：Arsenal、Real Madrid、Napoli、PSG 的具体球员排名仍需球员级数据验证。
3. **球员真实标签**：`player_truth_labels.parquet` 仍为空表，无法做球员级误差分析。
4. **Overfit gap 0.0537**：train-test 差距存在但不严重，可接受。
