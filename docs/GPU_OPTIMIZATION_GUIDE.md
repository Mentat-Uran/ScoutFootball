# GPU 重跑优化指南

## 目标

在 Windows RTX 5070 Ti 上重新运行评分权重优化器，使用新的组合目标函数（Spearman + NDCG@20 + 位置内排序一致性 + 极端样本惩罚 + 先验正则），修复 2526 holdout 覆盖问题，复盘误差案例。

## 前置条件

- Windows 10/11 + NVIDIA GPU（RTX 5070 Ti 或更高）
- Python 3.11+
- pip 安装依赖：`torch pandas numpy scipy pyarrow matplotlib plotly`

## 步骤

### 1. 克隆仓库

```bash
git clone https://github.com/Mentat-Uran/ScoutFootball_for_World_Cup.git
cd ScoutFootball_for_World_Cup
```

### 2. 安装依赖

```bash
uv sync --extra optimizer
```

Before a training run, verify the selected interpreter and raw Parquet inputs without writing an artifact:

```bash
PYTHONPATH=src uv run python -m scoutfootball optimizer-preflight --data-dir data
```

**RTX 5070 Ti (Blackwell, sm_120) 注意**：PyTorch 官方 cu121 稳定版不支持 sm_120
（会报 `CUDA error: no kernel image is available for execution on the device`）。
必须安装 `cu128` 版本：

```bash
pip install torch --index-url https://download.pytorch.org/whl/nightly/cu128
```

或使用 uv：

```bash
uv pip install pip
.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/nightly/cu128
```

### 3. 运行优化

**快速测试（几分钟）：**
```bash
python scripts/optimize_ratings_gpu.py --data_dir ./data --quick
```

**完整优化（推荐，10-30 分钟）：**
```bash
python scripts/optimize_ratings_gpu.py --data_dir ./data --steps 150 --pop 8 --patience 25
```

**高性能模式（如果 GPU 足够强）：**
```bash
python scripts/optimize_ratings_gpu.py --data_dir ./data --steps 200 --pop 12 --patience 30
```

### 4. 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--data_dir` | `./data` | 数据目录路径 |
| `--steps` | 150 | 优化迭代步数 |
| `--pop` | 8 | 种群大小（并行参数探索） |
| `--patience` | 25 | 早停耐心值 |
| `--lr` | 0.05 | 学习率 |
| `--seed` | 42 | 随机种子 |
| `--quick` | false | 快速模式（降低步数和种群） |
| `--no-viz` | false | 禁用可视化（服务器环境） |

### 5. 输出文件

优化完成后，以下文件会保存在 `data/gold/feature_store/`：

| 文件 | 说明 |
|---|---|
| `optimized_params.npy` | 优化后的 77 维参数向量 |
| `optimized_params_meta.json` | 参数元数据（指标、种子、输入 hash） |
| `player_ratings_optimized.parquet` | 更新后的球员评分 |
| `rating_holdout_predictions.parquet` | Holdout 预测结果 |
| `rating_league_metrics.parquet` | 联赛级指标 |
| `rating_team_coverage.parquet` | 球队覆盖率 |
| `rating_calibration_test.parquet` | 校准测试结果 |
| `rating_feature_importance.parquet` | 特征重要性（如果启用） |
| `rating_parameter_stability.parquet` | 参数稳定性（如果启用） |
| `rating_cv_metrics.parquet` | 交叉验证指标（如果启用） |

模型运行记录保存在 `data/models/runs/<timestamp>/`：
- `optimized_params.npy`
- `meta.json`

### 6. 提交结果

```bash
cd ScoutFootball_for_World_Cup
git add data/gold/feature_store/optimized_params.npy
git add data/gold/feature_store/optimized_params_meta.json
git add data/gold/feature_store/player_ratings_optimized.parquet
git add data/gold/feature_store/rating_holdout_predictions.parquet
git add data/gold/feature_store/rating_league_metrics.parquet
git add data/gold/feature_store/rating_team_coverage.parquet
git add data/gold/feature_store/rating_calibration_test.parquet
git add data/gold/feature_store/rating_feature_importance.parquet
git add data/gold/feature_store/rating_parameter_stability.parquet
git add data/gold/feature_store/rating_cv_metrics.parquet
git add data/models/runs/
git commit -m "feat: GPU 优化结果（RTX 5070 Ti, steps=X, pop=Y）"
git push origin main
```

## 已知问题

### 1. 2526 holdout 覆盖为 0

**问题：** 本地测试集（2526 赛季）的 Football-Data 球队名与评分侧不匹配，导致 team_coverage=0。

**解决方案：** 优化器已内置 alias patch（见 `optimize_ratings_gpu.py` 中的 `TEAM_ALIASES`）。如果仍有问题，检查输出的 `rating_team_coverage.parquet`，手动添加缺失的 alias。

### 2. 位置分布不均

**问题：** CM 权重过高（0.54），ST 攻击权重过低（0.086）。

**解决方案：** 优化器已加入位置多样性约束。检查输出的 `optimized_params_meta.json` 中的 `position_weights` 部分。

### 3. 误差案例

需要复盘的球队：
- Everton（出勤捷径高估）
- Stuttgart（弱联赛顶端）
- Hoffenheim（弱联赛顶端）
- Rennes（弱联赛顶端）
- Napoli（联赛强度偏差）
- Real Madrid（明星球员出勤）
- Arsenal（球队聚合被拉拽）
- PSG（弱联赛顶端）

优化完成后，检查 `rating_holdout_predictions.parquet` 中这些球队的排名变化。

## 组合目标权重

当前权重（可在命令行覆盖）：

| 维度 | 权重 | 说明 |
|---|---|---|
| Spearman | 0.50 | 排序一致性 |
| NDCG@20 | 0.20 | Top-20 排名质量 |
| 位置内排序 | 0.15 | 同位置球员相对排序 |
| 极端惩罚 | 0.10 | 防止极端高估/低估 |
| 先验正则 | 0.05 | 参数平滑 |

## 预期结果

- Holdout Spearman > 0.65（当前 GPU 最佳：0.7952）
- Holdout Pearson > 0.60（当前 GPU 最佳：0.6251）
- 联赛分布均衡（EPL 10+, Bundesliga 8+, La Liga 5+）
- 位置分布改善（CM 权重降低，ST 权重提高）
- 误差案例排名变化记录
