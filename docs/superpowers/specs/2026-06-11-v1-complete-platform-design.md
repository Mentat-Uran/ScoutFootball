# v1.0 完整分析平台设计

## 目标

将 ScoutFootball 从当前状态推进到 v1.0 完整分析平台：5 大联赛数据完整、评分模型达标（Spearman ≥0.75）、前端全部接真实数据、Dixon-Coles 校准闭环、CI/CD 自动化、macOS + Windows 桌面应用 + 网页云端访问。

## 推进策略

数据→模型→产品→基建，Phase 之间有依赖，Phase 内部可并行。

## Phase 1: 数据层补全

### 1.1 Football-Data 10 赛季合并
- **现状**：`combined_results.parquet` 仅 4 赛季（2223-2526），7,081 行
- **目标**：10 赛季（1617-2526），raw CSV 已存在于 `data/raw/football_data/`
- **交付**：扩展后的 `combined_results.parquet`，更新 alias 映射
- **验证**：行数约 17,000+，5 大联赛每赛季 coverage ≥0.95

### 1.2 Transfermarkt 身价导入
- **现状**：`data/raw/transfermarkt/player_market_value.csv` 和 `player_profiles.csv` 已存在但未入 pipeline
- **目标**：pipeline 自动读取 Transfermarkt CSV，产出球员身价时序
- **交付**：`player_market_values.parquet`，adapter 代码接入 pipeline
- **验证**：身价数据行数 ≥30,000，覆盖 5 大联赛主力球员

### 1.3 FBref 扩展表实际运行
- **现状**：适配器代码已写（`fbref_soccerdata.py`），从未运行
- **目标**：misc/defensive/passing/possession/playing_time/keeper/keeper_adv 7 种表入库
- **交付**：`data/raw/fbref/` 下 7 种 parquet 文件
- **依赖**：需 Selenium 环境，建议在 Windows GPU 服务器运行
- **验证**：每种表行数 ≥10,000

### 1.4 防守/控球特征入评分矩阵
- **现状**：`rating_feature_matrix.parquet` 8,141 行，防守/控球字段全部 fallback 为位置中位数
- **目标**：新增 15+ 防守/控球/传球特征，missing flag 标记
- **交付**：扩展后的 `rating_feature_matrix.parquet` + 更新 manifest
- **依赖**：1.3
- **验证**：新字段 missing rate < 0.30（5 大联赛主力球员）

### 1.5 StatsBomb events → SPADL 转换
- **现状**：`events_all.parquet` 7,744,412 行原始事件，SPADL schema 已定义但转换未实现
- **目标**：events → SPADL/atomic-SPADL 标准化动作表
- **交付**：`actions_all.parquet`（SPADL 格式），`actions_atomic.parquet`（atomic-SPADL 格式）
- **验证**：动作行数约为事件数的 60-70%，字段符合 SPADL 规范

### 1.6 球员真实标签填充
- **现状**：`player_truth_labels.parquet` 0 行
- **目标**：≥500 球员分档标签（Transfermarkt 身价分档 + 奖项 + 联赛级别 + 人工校准）
- **交付**：填充后的 `player_truth_labels.parquet`
- **依赖**：1.2（身价数据）
- **验证**：行数 ≥500，覆盖 5 大联赛各位置 Top 20

### 1.7 世界杯真实数据
- **现状**：4 个世界杯页面全用 demo 数据
- **目标**：48 队真实阵容 + 赛程 + 小组积分 + 预测
- **交付**：`data/raw/worldcup/` 下真实数据文件，替换 demo
- **验证**：48 队每队 23-26 人真实球员，赛程与 FIFA 官方一致

### 1.8 文档同步
- **现状**：DATA_STATUS_REPORT、AGENTS.md 数据行数与实际严重不符
- **目标**：所有文档数据行数与实际一致
- **交付**：更新后的 DATA_STATUS_REPORT.md、AGENTS.md
- **依赖**：1.1-1.7

## Phase 2: 评分模型达标

### 2.1 v1.3.1 GPU 完整重跑
- **现状**：league-bias loss 只做了只读复算，points MAE 从 11.55 降到 9.44（只读验证）
- **目标**：完整 GPU 重跑，参数优化 + 误差复盘
- **交付**：新 `optimized_params.npy` + meta.json + 误差案例报告
- **依赖**：Phase 1（新数据入矩阵后重跑才有意义）
- **验证**：holdout Spearman ≥0.75，强队偏差 ≤±15

### 2.2 Bundesliga coverage 修复
- **现状**：0.778
- **目标**：1.00
- **交付**：补齐 alias 映射
- **依赖**：2.1
- **验证**：Bundesliga coverage = 1.00

### 2.3 全量 xT 计算
- **现状**：3,740 行 xT 样本
- **目标**：774 万事件 → 全量 xT 动作价值
- **交付**：`player_action_value.parquet` 扩展到全量
- **依赖**：1.5（SPADL 转换）
- **验证**：行数 ≥30,000（球员赛季粒度）

### 2.4 VAEP 实现
- **现状**：未实现
- **目标**：SPADL → VAEP/Atomic-VAEP
- **交付**：VAEP 评分代码 + `player_vaep.parquet`
- **依赖**：2.3
- **验证**：VAEP 评分与 xT 排名相关性 ≥0.5，Top 10 球员符合直觉

### 2.5 评分特征增强
- **现状**：评分矩阵无 xT/VAEP/防守/控球特征
- **目标**：多维度特征接入评分矩阵
- **交付**：扩展后的 `rating_feature_matrix.parquet`
- **依赖**：2.3, 1.4
- **验证**：特征重要性中 xT/VAEP 特征进入 Top 10

### 2.6 神经网络候选对比
- **现状**：MLP 入口已实现但标签为空跳过
- **目标**：标签填充后 MLP vs baseline 同口径评估
- **交付**：对比报告 + 模型运行登记
- **依赖**：1.6, 2.5
- **验证**：MLP 不劣于 baseline（Spearman 差距 ≤0.02）

### 2.7 Dixon-Coles 校准
- **现状**：基础版已实现，无 time decay 和校准
- **目标**：time decay + 概率校准闭环
- **交付**：校准后的预测模型 + Brier/RPS 指标
- **依赖**：2.1（评分数据用于预测特征）
- **验证**：Brier score < 0.25，RPS < 0.20

### 2.8 模型评估文档更新
- **现状**：EVALUATION.md 大部分完成，误差案例待补
- **目标**：完整评估文档 + 误差案例复盘
- **交付**：更新后的 EVALUATION.md + MODEL_CARD.md
- **依赖**：2.1-2.7

## Phase 3: 产品层闭环

### 3.1 前端全部 mock→真实
- **现状**：部分页面仍用 mock 数据
- **目标**：所有页面走 FastAPI 契约
- **交付**：无 mock 残留的前端代码
- **依赖**：Phase 2
- **验证**：API OFFLINE 时显示降级提示，ONLINE 时全部真实数据

### 3.2 世界杯 4 页面真实数据
- **现状**：demo/混合数据
- **目标**：阵容/赛程/概率/对比全真实
- **交付**：4 个页面全部接真实后端
- **依赖**：1.7, 2.7
- **验证**：48 队真实球员，预测基于真实评分

### 3.3 球员对比增强
- **现状**：基础列表
- **目标**：同位置百分位 + 雷达叠加 + 趋势线
- **交付**：增强的球员对比页面
- **依赖**：2.5
- **验证**：选择两个球员后显示百分位对比表和雷达图

### 3.4 预测卡增强
- **现状**：基础选择器
- **目标**：比分矩阵 + 校准曲线 + 概率展示
- **交付**：增强的预测页面
- **依赖**：2.7
- **验证**：选择两队后显示比分矩阵和胜/平/负概率

### 3.5 战术板 GIF 导出
- **现状**：PNG/PDF/WebM/MP4 已有
- **目标**：GIF 格式支持
- **交付**：GIF 导出功能
- **验证**：导出的 GIF 可正常播放

### 3.6 球员档案端点增强
- **现状**：基础评分
- **目标**：位置内指标 + 低置信度原因 + 趋势
- **交付**：增强的 `/players/{name}` 端点
- **依赖**：2.5
- **验证**：返回位置内百分位、置信度标签、3 赛季趋势

### 3.7 动作价值全量端点
- **现状**：返回 3,740 行样本
- **目标**：返回全量 xT/VAEP 数据
- **交付**：增强的 `/action-values` 端点
- **依赖**：2.4
- **验证**：返回数据行数 ≥30,000

## Phase 4: 基础设施

### 4.1 GitHub Actions CI
- **现状**：完全缺失
- **目标**：lint + test + build 自动化
- **交付**：`.github/workflows/ci.yml`
- **依赖**：Phase 3
- **验证**：PR 提交自动触发 CI，lint 和 test 全绿

### 4.2 Windows 桌面应用
- **现状**：只有 macOS arm64
- **目标**：Windows x64 .exe 打包 + 自动更新
- **交付**：Windows 构建脚本 + .exe 产物
- **依赖**：4.1
- **验证**：在 Windows 10/11 上安装运行正常

### 4.3 云端部署
- **现状**：无
- **目标**：Streamlit Cloud 免费部署
- **交付**：部署配置 + 访问 URL
- **依赖**：4.1
- **验证**：公网可访问，数据加载正常

### 4.4 集成测试
- **现状**：只有单元测试
- **目标**：pipeline 端到端集成测试
- **交付**：`tests/integration/` 目录
- **依赖**：4.1
- **验证**：ingest → build-features → train 端到端通过

## 不在 v1.0 范围内

- Docker 化（后续版本考虑）
- 跨供应商 schema 标准化（P6）
- 球探人工标注回灌（P7）
- 空间/视频/离球研究（P8）
- 3D/门后视角
- 实时协作
- 视频叠画/tracking 导入

## 风险

1. **FBref Selenium 采集**：可能被反爬限制，需低频+缓存策略
2. **GPU 重跑**：需 RTX 5070 Ti 环境，本地无法执行
3. **真实标签质量**：Transfermarkt 身价分档只是代理标签，非真实影响力
4. **VAEP 计算量**：774 万事件训练 VAEP 模型可能需要数小时
5. **云端部署数据**：Streamlit Cloud 免费版存储有限，大 parquet 文件可能需要外部存储
