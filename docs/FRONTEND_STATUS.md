# Scoutlab Liquid Glass 前端开发状态追踪

## 📅 项目愿景
为 Scoutlab 提供基于 macOS 26/iOS 26 “液态玻璃”美学的前端交互。特点包含：超高折射率毛玻璃 (`backdrop-filter: blur(40px)`)、流体物理交互、Mesh Gradient 动态光影、以及带有降级容错（针对低置信度数据的“冰霜”效果）的内容呈现。

## 📍 当前进度 (初始阶段)
- [x] **架构设计**: 确立了液态玻璃的设计规范。
- [x] **原型构建**: 初始化 HTML/CSS 原型，搭建了侧边栏与液态卡片结构。
- [x] **渐变色升级**: 舍弃花哨色彩，采用更加极简、高级的深空灰/钛银配色流体网格。
- [x] **浅色/深色主题**: 增加了浅色(Light)与深色(Dark)无缝切换，CSS自适应光晕、阴影、背板颜色，连带ECharts图表动态变色。
- [x] **双语切换 (i18n)**: 增加中英文切换环境，支持通过点击一键切换界面的本地化呈现。
- [x] **引入可视化图表**: 已接入 ECharts，完成针对多维指标能力画像的环形雷达图渲染。
- [x] **模拟数据读取结构**: 在界面中集成了数据表视图(Data Grid)，保留了 Parquet 数据源的 `mockFetchData()` 对接逻辑。
- [ ] **框架引入**: 计划引入 Vue/React/Next.js 以完全接管路由和流体动画 (Framer Motion)。
- [ ] **API 联调**: 将 FastAPI 与现有的 `src/scoutlab/` 生成的 Parquet 产物完全连接，提供给前端读取。

## 🧩 核心功能模块实现表
| 模块 | 功能描述 | 状态 | 涉及组件 (前端) |
| :--- | :--- | :--- | :--- |
| **导航侧边栏** | macOS 浮动胶囊面板 | 🚧 进行中 | `Sidebar` / `GlassNav` |
| **球员库/对比** | 搜索球员，滑动阻尼，灵动岛对比提示 | ⏳ 待开发 | `DataGrid` / `CompareIsland` |
| **全息档案页** | 展示雷达图、3D多边形、低置信度冰霜效果 | ⏳ 待开发 | `ProfileSheet` / `GlassRadar` |
| **比分预测卡** | 液态量杯动画、随时间衰减的概率流 | ⏳ 待开发 | `MatchPredictor` |
| **管线暗房** | 控制训练流程，脉冲发光效果 | ⏳ 待开发 | `PipelineDAG` |

## 🎨 Token 与样式规范
- **毛玻璃**: `background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(40px);`
- **边框**: `border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: inset 0 0 20px rgba(255,255,255,0.05);`
- **流体动画 (Spring)**: 阻尼弹簧效果，快速响应，平滑回弹。