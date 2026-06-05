# Tasks

- [ ] Task 1: GPU 服务器新增文件下载端点
  - [ ] 1.1 在 `gpu_server.py` 新增 `GET /download/<path>` 端点，限定只允许下载 `gold/feature_store/` 和 `models/runs/` 下的文件
  - [ ] 1.2 在 `gpu_client.py` 新增 `download` 子命令，下载 `optimized_params.npy`、`optimized_params_meta.json`、`player_ratings_optimized.parquet`、`gpu_optimize_result.json` 到本地对应目录

- [ ] Task 2: 评分导出到 DuckDB 命令
  - [ ] 2.1 在 `src/scoutlab/storage/duckdb_io.py` 新增 `create_ratings_database()` 函数，创建 4 张表（player_ratings, model_meta, league_metrics, team_coverage）
  - [ ] 2.2 在 `src/scoutlab/__main__.py` 新增 `export-ratings` 子命令入口
  - [ ] 2.3 `export-ratings` 读取 `optimized_params.npy` + `rating_feature_matrix.parquet`（或 `player_ratings_optimized.parquet`），写入 DuckDB
  - [ ] 2.4 处理 DuckDB 不存在或参数文件缺失的错误提示

- [ ] Task 3: 前端数据加载
  - [ ] 3.1 在 `data_loader.py` 新增 `load_player_ratings()` 函数，从 DuckDB 读取球员评分
  - [ ] 3.2 支持按 position、league、team 筛选参数
  - [ ] 3.3 DuckDB 不存在时 fallback 到 Parquet 或 demo 数据

- [ ] Task 4: 同步 GPU 服务器产物到本地
  - [ ] 4.1 上传更新后的 `gpu_server.py` 到 Windows 服务器
  - [ ] 4.2 重启服务器
  - [ ] 4.3 运行 `gpu_client.py download` 下载评分产物
  - [ ] 4.4 运行 `scoutlab export-ratings` 生成 DuckDB 数据库

- [ ] Task 5: 验证
  - [ ] 5.1 `ruff check` 零错误
  - [ ] 5.2 `pytest` 全部通过
  - [ ] 5.3 DuckDB 数据库文件存在且包含 4 张表
  - [ ] 5.4 `load_player_ratings()` 能正确返回数据

# Task Dependencies
- Task 2 依赖 Task 1（需要先下载产物到本地）
- Task 3 依赖 Task 2（需要 DuckDB 数据库存在）
- Task 4 依赖 Task 1 + Task 2（需要代码完成后再同步到服务器）
- Task 5 依赖 Task 4（需要实际数据验证）
