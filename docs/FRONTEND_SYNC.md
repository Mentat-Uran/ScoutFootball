# 前后端三组件统一同步分析

## 1. 架构现状

### 三个组件关系图

```
┌─────────────────────────────────────────────────────────┐
│                    ScoutFootball 项目                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────┐      ┌───────────────────────┐ │
│  │   Streamlit 前端      │      │  Liquid Glass 前端    │ │
│  │   (12个页面)          │      │   (7个视图)           │ │
│  │   直接读本地数据      │      │   通过API/mock        │ │
│  └──────────────┬───────┘      └───────────┬───────────┘ │
│                 │                           │            │
│                 └──────────────┬────────────┘            │
│                                │                         │
│                  ┌─────────────▼─────────────┐          │
│                  │    FastAPI 后端服务       │          │
│                  │  api_server.py + api.py   │          │
│                  │     + data_loader.py      │          │
│                  └─────────────┬─────────────┘          │
│                                │                         │
│                  ┌─────────────▼─────────────┐          │
│                  │    本地数据仓库           │          │
│                  │  Parquet / DuckDB        │          │
│                  └───────────────────────────┘          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## 2. 视图映射关系

### 两个前端与后端的对应表

| Liquid Glass 视图 | Streamlit 页面 | 后端 API | 状态 |
|------------------|--------------|---------|------|
| 总览 | 无 | `/artifacts`, `/health`, `/ratings/meta` | ✅ API 已有 |
| 球员 | Player Comparison, Position Percentiles, Player Rankings | `/ratings`, `/player/{name}/profile` | ✅ API 已有 |
| 身价 | Value Scatter, Value Deviation | `/value-summary` | ✅ API 已有 |
| 预测 | Score Matrix, Match Prediction | `/prediction/{home}/{away}` | ✅ API 已有 |
| 球探 | 无 | `/review-queue`, `/teams` | ✅ API 已有 |
| 动作价值 | 无 | 待定 | ⚠️ 待实现 |
| 报告 | 无 | `/model-runs` | ✅ API 已有 |
| - | World Cup Schedule/Squads/Compare/Probability | 待定 | 🆕 世界杯模块 |

## 3. 发现的冲突点

### 3.1 数据源不一致

| 组件 | 数据源 | 问题 |
|-----|--------|-----|
| Streamlit | 直接调用 `data_loader.py` | 需要同时兼容 demo/真实数据 |
| Liquid Glass | Mock 数据 + API 占位 | 需要正确连接到 API |
| 后端 API | 统一 `data_loader.py` | 已有，但需要完善端点 |

### 3.2 功能覆盖差异

- **Streamlit 独有功能**：世界杯 4 个页面、Player Comparison、Trends
- **Liquid Glass 独有布局**：7 视图分析工作台、数据健康看板
- **API 已有但未完全使用**：Model Runs、Review Queue

### 3.3 命名不一致

| Streamlit | Liquid Glass | 说明 |
|-----------|--------------|-----|
| Value vs Performance | 身价偏离 | 同一功能 |
| Score Matrix | 比分矩阵 | 同一功能 |
| Player Rankings | 球员池 | 同一功能 |

## 4. 统一解决方案

### 4.1 数据源统一

1. **Streamlit 保持现状**：直接使用 `data_loader.py`，这是最直接高效的方式
2. **Liquid Glass 完善 API 连接**：让它真正连接到 `/api/*` 端点
3. **数据加载统一**：两个前端最终都通过 `data_loader.py` 的逻辑

### 4.2 功能双向补充

1. **Streamlit 增加**：Model Runs 页面、Review Queue 页面
2. **Liquid Glass 增加**：世界杯相关视图（或标记为 beta）
3. **API 端点完善**：补充世界杯数据接口

### 4.3 启动方式统一

1. **统一启动脚本**：可以选择启动 API + Liquid Glass，或者只启动 Streamlit
2. **API 服务同时提供**：FastAPI 提供数据 + 静态文件服务
