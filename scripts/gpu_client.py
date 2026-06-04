#!/usr/bin/env python3
"""
ScoutLab GPU 计算客户端 — 在 Mac 上运行，发送任务给 Windows GPU 服务器

使用:
  # 健康检查
  python gpu_client.py --server http://192.168.1.100:8420 health

  # 运行优化
  python gpu_client.py --server http://192.168.1.100:8420 optimize --pop 32 --steps 500

  # 查询球员评分
  python gpu_client.py --server http://192.168.1.100:8420 score "Mbappe"

  # 批量 Top N
  python gpu_client.py --server http://192.168.1.100:8420 top --n 20 --position ST

  # 上传数据
  python gpu_client.py --server http://192.168.1.100:8420 upload ./data.zip
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("需要 requests 库: pip install requests")
    sys.exit(1)


# ── 工具函数 ─────────────────────────────────────────────────────────────


def _url(server: str, path: str) -> str:
    return f"{server.rstrip('/')}{path}"


def _post(server: str, path: str, data: dict, timeout: int = 600) -> dict:
    resp = requests.post(_url(server, path), json=data, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _get(server: str, path: str) -> dict:
    resp = requests.get(_url(server, path), timeout=10)
    resp.raise_for_status()
    return resp.json()


# ── 命令 ─────────────────────────────────────────────────────────────────


def cmd_health(server: str, args):
    """健康检查。"""
    data = _get(server, "/health")
    print("=" * 50)
    print("ScoutLab GPU 服务器状态")
    print("=" * 50)
    print(f"  状态:       {data['status']}")
    print(f"  设备:       {data['device']}")
    print(f"  GPU:        {data.get('gpu_name', 'N/A')}")
    print(f"  CUDA:       {data['cuda_available']}")
    print(f"  MPS:        {data['mps_available']}")
    print(f"  数据目录:   {data['data_dir']}")
    print(f"  数据已加载: {data['data_loaded']}")
    print("=" * 50)


def cmd_optimize(server: str, args):
    """运行优化。"""
    payload = {
        "steps": args.steps,
        "lr": args.lr,
        "pop": args.pop,
    }
    print(f"发送优化请求到 {server}...")
    print(f"  步数: {args.steps}, 学习率: {args.lr}, 种群: {args.pop}")
    print(f"  预计耗时: {args.pop * args.steps // 100}~{args.pop * args.steps // 30} 秒")
    print()

    # 提交异步任务
    resp = _post(server, "/optimize", payload, timeout=30)
    job_id = resp["job_id"]
    print(f"  任务已提交: {job_id}")
    print(f"  轮询结果中...")

    # 轮询等待完成
    t0 = time.time()
    while True:
        time.sleep(3)
        try:
            status = _get(server, f"/jobs/{job_id}")
        except Exception:
            continue

        if status["status"] == "done":
            data = status["result"]
            break
        elif status["status"] == "error":
            print(f"  优化失败: {status['error']}")
            return
        else:
            elapsed_so_far = int(time.time() - t0)
            print(f"  [{elapsed_so_far}s] 仍在运行...", end="\r")

    elapsed = time.time() - t0

    print("=" * 60)
    print("优化结果")
    print("=" * 60)
    print(f"  设备:        {data['device']}")
    print(f"  球员数:      {data['n_players']}")
    print(f"  球队赛季:    {data['n_team_seasons']}")
    print(f"  耗时:        {data['elapsed_seconds']}s (本地 {elapsed:.1f}s)")
    if data.get("train_seasons") or data.get("test_seasons"):
        print(f"  训练赛季:    {', '.join(data.get('train_seasons', []))}")
        print(f"  测试赛季:    {', '.join(data.get('test_seasons', []))}")
    print()
    print(f"  Holdout 基线 Spearman:  {data['baseline_spearman']:.4f}")
    print(f"  Holdout 基线 Pearson:   {data['baseline_pearson']:.4f}")
    print(f"  Holdout 优化 Spearman:  {data['spearman']:.4f}")
    print(f"  Holdout 优化 Pearson:   {data['pearson']:.4f}")
    if data.get("train_spearman") is not None:
        print(f"  Train 优化 Spearman:    {data['train_spearman']:.4f}")
    if data.get("overfit_rank_loss_gap") is not None:
        print(f"  过拟合 rank loss gap:   {data['overfit_rank_loss_gap']:+.4f}")
    print(f"  Holdout 提升:           Spearman {data['spearman_improvement']:+.4f}  "
          f"Pearson {data['pearson_improvement']:+.4f}")
    print()

    # 各联赛
    if data.get("per_league"):
        print("  Holdout 各联赛相关性:")
        for league, stats in sorted(data["per_league"].items()):
            calib = stats.get("calibration_mae")
            calib_text = f"  calib_MAE={calib:.2f}" if calib is not None else ""
            print(
                f"    {league:<22} Spearman={stats['spearman']:.3f}  "
                f"Pearson={stats['pearson']:.3f}{calib_text}  N={stats['n']}"
            )
        print()

    # 权重表
    if data.get("position_weights"):
        pw = data["position_weights"]
        dims = list(next(iter(pw.values())).keys())
        print(f"  {'位置':<5}", end="")
        for d in dims:
            print(f" {d:>10}", end="")
        print()
        print("  " + "-" * (5 + 11 * len(dims)))
        for pos in ["ST", "W", "AM", "CM", "DM", "FB", "CB", "GK"]:
            if pos in pw:
                print(f"  {pos:<5}", end="")
                for d in dims:
                    print(f" {pw[pos][d]:>10.4f}", end="")
                print()
        print()

    # 保存参数
    if data.get("params_base64"):
        output_dir = Path("./data/gold/feature_store")
        output_dir.mkdir(parents=True, exist_ok=True)
        params_path = output_dir / "optimized_params.npy"

        try:
            import io
            import numpy as np

            buf = base64.b64decode(data["params_base64"])
            arr = np.load(io.BytesIO(buf), allow_pickle=False)
            np.save(params_path, arr)
            print(f"  参数已保存: {params_path}")
        except ImportError:
            # 没有 numpy 时保存为 base64 文件
            b64_path = output_dir / "optimized_params.b64"
            b64_path.write_text(data["params_base64"])
            print(f"  参数已保存 (base64): {b64_path}")
            print(f"  提示: pip install numpy 后可用 np.load 加载")

    print("=" * 60)


def cmd_score(server: str, args):
    """查询球员评分。"""
    payload = {"player_name": args.name}
    if args.team:
        payload["team"] = args.team
    if args.league:
        payload["league"] = args.league
    if args.season:
        payload["season"] = args.season

    try:
        data = _post(server, "/score", payload)
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            print(f"未找到球员: {args.name}")
        else:
            print(f"错误: {e}")
        return

    print(f"  球员: {data['player']}")
    print(f"  评分: {data['score']}")
    print(f"  位置: {data['sub_position']}")
    print(f"  球队: {data['team']}")
    print(f"  联赛: {data['league']}")
    print(f"  赛季: {data['season']}")


def cmd_top(server: str, args):
    """批量查询 Top N。"""
    payload = {"top_n": args.n}
    if args.position:
        payload["position"] = args.position
    if args.league:
        payload["league"] = args.league
    if args.season:
        payload["season"] = args.season

    data = _post(server, "/scores/bulk", payload)

    if not data["players"]:
        print("无结果")
        return

    title = f"Top {data['count']}"
    if args.position:
        title += f" ({args.position})"
    if args.league:
        title += f" - {args.league}"
    print(title)
    print("-" * 75)
    print(f"{'#':>4}  {'球员':<28} {'球队':<20} {'位置':<4} {'评分':>6}")
    print("-" * 75)
    for i, p in enumerate(data["players"], 1):
        print(f"{i:>4}  {p['player']:<28} {p['team']:<20} {p['position']:<4} {p['score']:>6.1f}")


def cmd_upload(server: str, args):
    """上传数据文件。"""
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"文件不存在: {filepath}")
        return

    print(f"上传 {filepath} ({filepath.stat().st_size / 1024 / 1024:.1f} MB)...")
    with open(filepath, "rb") as f:
        resp = requests.post(
            _url(server, "/upload-data"),
            files={"file": (filepath.name, f)},
            timeout=600,
        )
    resp.raise_for_status()
    data = resp.json()
    print(f"  {data['message']}")


def cmd_reload(server: str, args):
    """强制重载数据。"""
    data = _post(server, "/reload-data", {})
    print(f"  {data['message']}")


# ── 主入口 ───────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="ScoutLab GPU 计算客户端")
    parser.add_argument(
        "--server",
        type=str,
        default="http://localhost:8420",
        help="GPU 服务器地址 (默认 http://localhost:8420)",
    )
    sub = parser.add_subparsers(dest="command")

    # health
    sub.add_parser("health", help="服务器状态")

    # optimize
    p_opt = sub.add_parser("optimize", help="运行优化")
    p_opt.add_argument("--steps", type=int, default=500, help="每组步数")
    p_opt.add_argument("--lr", type=float, default=0.05, help="学习率")
    p_opt.add_argument("--pop", type=int, default=32, help="种群大小")

    # score
    p_score = sub.add_parser("score", help="查询球员评分")
    p_score.add_argument("name", help="球员名 (模糊匹配)")
    p_score.add_argument("--team", help="球队名")
    p_score.add_argument("--league", help="联赛")
    p_score.add_argument("--season", help="赛季")

    # top
    p_top = sub.add_parser("top", help="批量 Top N")
    p_top.add_argument("--n", type=int, default=20, help="数量")
    p_top.add_argument("--position", help="位置 (ST/W/AM/CM/DM/FB/CB/GK)")
    p_top.add_argument("--league", help="联赛")
    p_top.add_argument("--season", help="赛季")

    # upload
    p_up = sub.add_parser("upload", help="上传数据文件")
    p_up.add_argument("file", help="文件路径")

    # reload
    sub.add_parser("reload", help="强制重载数据")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cmd_map = {
        "health": cmd_health,
        "optimize": cmd_optimize,
        "score": cmd_score,
        "top": cmd_top,
        "upload": cmd_upload,
        "reload": cmd_reload,
    }

    try:
        cmd_map[args.command](args.server, args)
    except requests.ConnectionError:
        print(f"连接失败: {args.server}")
        print("请确认:")
        print("  1. Windows 服务器已启动 (python gpu_server.py)")
        print("  2. IP 地址和端口正确")
        print("  3. 防火墙允许该端口")
    except requests.HTTPError as e:
        print(f"HTTP 错误: {e}")
        if e.response is not None:
            print(f"  响应: {e.response.text[:500]}")


if __name__ == "__main__":
    main()
