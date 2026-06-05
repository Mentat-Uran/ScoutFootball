# Tasks

- [x] Task 1: 评分特征矩阵契约与缺失字段处理
  - [x] 1.1 在 `src/scoutlab/features/rating_matrix.py` 中新增 `mark_missing_fields()` 函数，为防守、控球、xT/VAEP、门将高阶字段添加 `_missing` 布尔标记
  - [x] 1.2 新增 `fill_missing_with_position_median()` 函数，缺失数值字段使用位置内中位数填充而非 0
  - [x] 1.3 新增 `build_rating_feature_matrix()` 函数，整合数值特征、位置/联赛类别、数据源覆盖标记、缺失字段标记
  - [x] 1.4 新增 `write_feature_manifest()` 函数，输出 feature manifest JSON（列名、类型、来源、缺失率）
  - [x] 1.5 在 `pipeline.py` 的 `run_build_features` 中集成特征矩阵和 manifest 输出
  - [x] 1.6 编写单元测试验证缺失标记、fallback 值和 manifest 输出

- [x] Task 2: Finishing Shrinkage
  - [x] 2.1 在 `src/scoutlab/features/rating_matrix.py` 中新增 `compute_finishing_shrinkage()` 函数，实现经验贝叶斯 shrinkage
  - [x] 2.2 在特征矩阵构建中添加 `finishing_shrunk` 和 `finishing_raw` 列
  - [x] 2.3 编写单元测试验证小样本和大样本球员的 shrinkage 行为

- [x] Task 3: Coverage 低置信度规则
  - [x] 3.1 在评分产物中为每个 league-season 添加 `coverage` 和 `confidence_level` 字段
  - [x] 3.2 实现置信度分级逻辑：>=0.90 正常、0.70-0.90 中置信度、<0.70 低置信度
  - [x] 3.3 在 Streamlit 页面中显示置信度标记（`display_confidence_badge`）
  - [x] 3.4 编写单元测试验证分级逻辑

- [x] Task 4: 出勤捷径诊断报告
  - [x] 4.1 新增 `src/scoutlab/evaluation/availability_diagnostic.py`，实现置换重要性计算
  - [x] 4.2 实现按位置 availability 权重分布统计
  - [x] 4.3 实现球队聚合权重分布统计
  - [x] 4.4 实现 Top 20 出勤驱动球员识别（availability 权重贡献 > 50%）
  - [x] 4.5 在 `pipeline.py` 的 `run_weekly_train` 中集成诊断报告输出
  - [x] 4.6 编写单元测试验证诊断报告输出格式和内容

- [x] Task 5: 位置内指标和解释模板
  - [x] 5.1 新增 `src/scoutlab/evaluation/position_metrics.py`，定义 8 个位置的核心维度
  - [x] 5.2 实现位置内 percentile rank 计算
  - [x] 5.3 实现自然语言解释模板生成
  - [x] 5.4 实现位置内榜单和跨位置总榜两个独立视图
  - [x] 5.5 编写单元测试验证各位置维度定义和 percentile 计算

- [x] Task 6: mplsoccer 集成与 pitch.py
  - [x] 6.1 在 `pyproject.toml` 中添加 mplsoccer 和 matplotlib 依赖
  - [x] 6.2 新增 `src/scoutlab/viz/pitch.py`，封装球场绘制、坐标系统
  - [x] 6.3 实现 shot map 绘制函数
  - [x] 6.4 实现 pass map 绘制函数
  - [x] 6.5 实现 heatmap 绘制函数
  - [x] 6.6 实现 pizza chart 绘制函数（基于 mplsoccer PyPizza，回退 matplotlib polar plot）
  - [x] 6.7 编写单元测试验证各绘图函数不抛异常

- [x] Task 7: 球员雷达/排名页
  - [x] 7.1 新增 `src/scoutlab/app/pages/6_Player_Rankings.py`
  - [x] 7.2 实现位置选择器和位置内 Top 20 榜单
  - [x] 7.3 集成 pizza chart 展示选中球员的位置内 percentile
  - [x] 7.4 实现球员详情卡（评分趋势、xG/xA、出勤、联赛强度调整）
  - [x] 7.5 添加低置信度提示（分钟不足、数据缺失等）
  - [x] 7.6 在 `streamlit_app.py` 中注册新页面

- [x] Task 8: 身价偏离榜
  - [x] 8.1 新增 `src/scoutlab/app/pages/7_Value_Deviation.py`
  - [x] 8.2 实现实际身价 vs 预测身价散点图
  - [x] 8.3 实现高估/低估 Top 20 列表
  - [x] 8.4 实现联赛和年龄段筛选
  - [x] 8.5 添加低置信度球员标记
  - [x] 8.6 在 `streamlit_app.py` 中注册新页面

- [x] Task 9: 比赛预测页
  - [x] 9.1 新增 `src/scoutlab/app/pages/8_Match_Prediction.py`
  - [x] 9.2 实现比赛列表（从 Football-Data 最新赛季读取）
  - [x] 9.3 实现主胜/平/客胜概率展示
  - [x] 9.4 实现比分分布图（基于 Poisson 模型）
  - [x] 9.5 添加模型置信度提示
  - [x] 9.6 在 `streamlit_app.py` 中注册新页面

- [x] Task 10: 低置信度提示集成
  - [x] 10.1 新增 `src/scoutlab/evaluation/confidence.py`，实现统一低置信度判断逻辑
  - [x] 10.2 在所有 Streamlit 页面中集成低置信度提示组件
  - [x] 10.3 编写单元测试验证置信度判断逻辑

- [x] Task 11: 集成测试与验证
  - [x] 11.1 运行 `uv run ruff check .` 确保代码风格通过（src/ 仅 4 个预存长行，非本次引入）
  - [x] 11.2 运行 `uv run pytest` 确保所有测试通过（250 passed，排除 torch 和 entities 预存问题）
  - [x] 11.3 `scoutlab info` 和 `scoutlab validate` 命令正常运行
  - [x] 11.4 验证 `scoutlab build-features` 输出新增产物（rating_feature_matrix.parquet + manifest）
  - [x] 11.5 验证 `scoutlab train` 输出诊断报告和位置内指标（pipeline 已集成）

# Task Dependencies
- Task 1 (特征矩阵) 是 Task 2 (finishing shrinkage)、Task 4 (诊断报告)、Task 5 (位置内指标) 的前置
- Task 2 (finishing shrinkage) 依赖 Task 1
- Task 3 (coverage 规则) 可与 Task 1 并行
- Task 4 (诊断报告) 依赖 Task 1
- Task 5 (位置内指标) 依赖 Task 1
- Task 6 (mplsoccer) 可与 Task 1-5 并行
- Task 7 (球员排名页) 依赖 Task 5 和 Task 6
- Task 8 (身价偏离榜) 依赖 Task 1 和 Task 3
- Task 9 (比赛预测页) 可与 Task 7/8 并行
- Task 10 (低置信度提示) 依赖 Task 3，与 Task 7/8/9 并行
- Task 11 (集成测试) 依赖所有其他 Task
