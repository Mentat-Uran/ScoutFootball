# 评分校准与展示增强 Spec

## Why
评分系统已完成第一轮反出勤捷径 guardrail（availability cap、ST/W quality cap、稳健球队聚合、team coverage），但 P0 仍有多个代码级改进未落地：出勤捷径诊断、特征矩阵契约、缺失字段处理、finishing shrinkage、位置内指标。同时 P1 展示层只有 5 个基础 Streamlit 页面，缺少 mplsoccer 足球专用图表、球员雷达/排名页、身价偏离榜和比赛预测页 3 个核心可截图页面。本 spec 将 P0 可本地完成的代码改进和 P1 展示增强合并为一个交付批次。

## What Changes
- 新增出勤捷径诊断报告模块，输出 minutes/starts/matches/availability 置换重要性、按位置 availability 权重、球队聚合权重分布
- 新增 coverage 低置信度规则：对 coverage < 0.90 的 league-season 禁止输出强排序结论，只允许低置信度诊断
- 新增评分特征矩阵契约，输出 `rating_feature_matrix.parquet`，包含数值特征、位置/联赛类别、数据源覆盖、缺失字段标记、输入文件 hash 和 feature manifest
- 修正缺失高阶字段处理：防守、控球、xT/VAEP、门将字段缺失时必须有 missing flag 和中性/低置信度 fallback，不能把缺失值 0 当成真实低能力
- 新增 finishing shrinkage：对 `goals - xG` 使用样本量 shrinkage，避免小样本过度放大射术信号
- 新增位置内指标和解释模板：GK/CB/FB/DM/CM/AM/W/ST 各位置输出进攻、防守、控球、推进、终结、可靠性解释
- 新增位置内榜单和跨位置总榜两个视图的切换能力
- 引入 mplsoccer 依赖，新增 `src/scoutlab/viz/pitch.py` 封装球场、坐标、shot map、pass map、heatmap 基础图
- 新增球员雷达/排名页：pizza chart（mplsoccer）、位置内 percentile、位置内 Top 20 榜单、球员详情卡
- 新增身价偏离榜：实际身价 vs 模型预测身价散点图、高估/低估 Top 20、联赛和年龄段筛选
- 新增比赛预测页：即将进行的比赛列表、主/客/平概率、比分分布图、模型置信度提示
- 增加低置信度提示：分钟不足、数据源缺失、位置重判不确定、事件样本不足

## Impact
- Affected specs: 评分层（P0）、产品可视化层（P1）
- Affected code:
  - `src/scoutlab/evaluation/` — 新增诊断报告
  - `src/scoutlab/features/` — 特征矩阵契约、缺失字段标记、finishing shrinkage
  - `src/scoutlab/models/` — 位置内指标、位置内/跨位置榜单视图
  - `src/scoutlab/viz/` — 新增 pitch.py，增强 radar.py
  - `src/scoutlab/app/pages/` — 新增 3 个核心页面
  - `src/scoutlab/app/data_loader.py` — 新增数据加载函数
  - `src/scoutlab/pipeline.py` — 集成新特征构建步骤
  - `pyproject.toml` — 新增 mplsoccer 依赖

## ADDED Requirements

### Requirement: 出勤捷径诊断报告
系统 SHALL 提供出勤捷径诊断报告，包含以下内容：
- minutes/starts/matches/availability 的置换重要性（permutation importance）
- 按位置的 availability 权重分布
- 球队聚合权重分布
- Top 20 出勤驱动球员列表（availability 权重贡献 > 50% 的球员）

#### Scenario: 生成诊断报告
- **WHEN** 运行 `scoutlab train` 或调用诊断报告函数
- **THEN** 输出包含置换重要性、权重分布和出勤驱动球员列表的诊断报告

### Requirement: Coverage 低置信度规则
系统 SHALL 对 coverage < 0.90 的 league-season 禁止输出强排序结论。具体规则：
- 评分产物中为每个 league-season 标注 coverage 和置信度等级
- coverage >= 0.90：正常输出
- 0.70 <= coverage < 0.90：标注"中置信度"，排序结论仅供参考
- coverage < 0.70：标注"低置信度"，只输出诊断样本，不输出排名

#### Scenario: 低覆盖率联赛处理
- **WHEN** 某联赛赛季 coverage 为 0.75
- **THEN** 评分产物中该联赛标注"中置信度"，Streamlit 页面显示提示

### Requirement: 评分特征矩阵契约
系统 SHALL 输出可复用的 `rating_feature_matrix.parquet`，包含：
- 数值特征列（赛季统计、xG/xA、出勤、联赛强度等）
- 位置/联赛类别列
- 数据源覆盖标记列（`_source_covered` 后缀）
- 缺失字段标记列（`_missing` 后缀）
- 输入文件 hash
- feature manifest JSON（列名、类型、来源、缺失率）

#### Scenario: 生成特征矩阵
- **WHEN** 运行 `scoutlab build-features`
- **THEN** 输出 `data/gold/feature_store/rating_feature_matrix.parquet` 和 `rating_feature_manifest.json`

### Requirement: 缺失高阶字段处理
系统 SHALL 对缺失的防守、控球、xT/VAEP、门将高阶字段进行标记和 fallback 处理：
- 缺失字段添加 `_missing` 布尔标记列
- 缺失数值字段使用位置内中位数作为 fallback（而非 0）
- 缺失字段对应的置信度降低
- 在评分解释中标注"该维度数据缺失，使用位置中位数填充"

#### Scenario: 防守数据缺失
- **WHEN** 某球员的抢断、拦截等防守字段全部缺失
- **THEN** 添加 `defense_missing=True`，防守数值使用位置内中位数填充，置信度标记为"低"

### Requirement: Finishing Shrinkage
系统 SHALL 对 finishing 信号使用样本量 shrinkage，避免小样本 `goals - xG` 过度放大射术信号。具体方法：
- 使用经验贝叶斯 shrinkage：`shrunk_finishing = (n / (n + K)) * raw_finishing + (K / (n + K)) * 0`
- K 为 shrinkage 因子，默认 50（约 5 场比赛的射门量级）
- n 为该球员的射门次数
- raw_finishing 为 `(goals - xG) / shots`

#### Scenario: 小样本球员 shrinkage
- **WHEN** 某球员仅 3 次射门，goals - xG = +1.0
- **THEN** shrunk_finishing 接近 0 而非 +1.0，避免小样本过度放大

### Requirement: 位置内指标和解释模板
系统 SHALL 为 GK/CB/FB/DM/CM/AM/W/ST 各位置提供位置内指标和解释模板：
- 每个位置定义 3-6 个核心维度（如 ST: 终结、推进、出勤、联赛强度；CB: 防守、出勤、联赛强度）
- 每个维度输出该位置内的 percentile rank
- 生成自然语言解释模板（如"该球员终结能力位于 ST 前 10%，但出勤可靠性仅前 50%"）

#### Scenario: ST 位置内指标
- **WHEN** 查看某 ST 球员的位置内指标
- **THEN** 输出终结、推进、出勤、联赛强度 4 个维度的 percentile rank 和自然语言解释

### Requirement: 位置内榜单和跨位置总榜
系统 SHALL 提供位置内榜单和跨位置总榜两个独立视图：
- 位置内榜单：同一位置球员的评分排名
- 跨位置总榜：所有位置球员的评分排名，带位置标签
- 两个视图均支持低置信度标记

#### Scenario: 切换榜单视图
- **WHEN** 在 Streamlit 页面选择"位置内榜单"
- **THEN** 显示选定位置的球员排名，带位置内 percentile

### Requirement: mplsoccer 集成
系统 SHALL 引入 mplsoccer 作为可视化增强库，同时保持 Plotly 现有交互图不回退：
- 新增 `src/scoutlab/viz/pitch.py`，封装球场绘制、坐标系统、shot map、pass map、heatmap
- pizza chart 使用 mplsoccer 的 PyPizza 实现
- 现有 Plotly 图表保持不变

#### Scenario: 绘制 pizza chart
- **WHEN** 调用 pizza chart 绘制函数
- **THEN** 使用 mplsoccer PyPizza 生成位置内 percentile 雷达图

### Requirement: 球员雷达/排名页
系统 SHALL 提供球员雷达/排名页，包含：
- 球员 pizza chart（mplsoccer PyPizza），展示位置内 percentile
- 位置内 Top 20 榜单
- 球员详情卡（评分趋势、xG/xA、出勤、联赛强度调整、低置信度提示）

#### Scenario: 查看球员排名
- **WHEN** 用户选择 ST 位置
- **THEN** 显示 ST 位置内 Top 20 榜单和选中球员的 pizza chart

### Requirement: 身价偏离榜
系统 SHALL 提供身价偏离榜页面，包含：
- 实际身价 vs 模型预测身价散点图
- 高估 Top 20 和低估 Top 20 列表
- 联赛和年龄段筛选
- 低置信度球员标记

#### Scenario: 查看高估球员
- **WHEN** 用户点击"高估 Top 20"
- **THEN** 显示模型预测身价远高于实际身价的 20 名球员

### Requirement: 比赛预测页
系统 SHALL 提供比赛预测页面，包含：
- 即将进行的比赛列表（从 Football-Data 最新赛季读取）
- 主胜/平/客胜概率
- 比分分布图（基于 Poisson 模型）
- 模型置信度提示（基于训练数据量和球队覆盖）

#### Scenario: 查看比赛预测
- **WHEN** 用户选择一场比赛
- **THEN** 显示主胜/平/客胜概率和最可能比分分布

### Requirement: 低置信度提示
系统 SHALL 在所有评分展示中增加低置信度提示：
- 分钟不足（< 450 分钟）
- 数据源缺失（关键维度 _missing=True）
- 位置重判不确定（粗位置映射置信度低）
- 事件样本不足（StatsBomb 覆盖不足）
- 联赛 coverage 低于 0.90

#### Scenario: 低分钟球员提示
- **WHEN** 某球员赛季出场 < 450 分钟
- **THEN** 页面显示"低置信度：出场时间不足"提示

## MODIFIED Requirements

### Requirement: build-features pipeline
`run_build_features` SHALL 在现有特征构建基础上，额外生成：
- `rating_feature_matrix.parquet`（含缺失标记和 fallback）
- `rating_feature_manifest.json`（列名、类型、来源、缺失率）
- finishing shrinkage 列（`finishing_shrunk`）

### Requirement: train pipeline
`run_weekly_train` SHALL 在现有训练基础上，额外输出：
- 出勤捷径诊断报告
- 位置内指标和解释模板
- coverage 低置信度标记

## REMOVED Requirements
无移除项。
