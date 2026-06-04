#!/usr/bin/env python3
"""
ScoutLab GPU 计算服务器 v3 — 在 Windows (RTX 5070 Ti) 上运行

启动:
  pip install fastapi uvicorn torch pandas numpy scipy pyarrow
  python gpu_server.py --data_dir ./data --port 8420

Mac 端发送任务:
  python gpu_client.py --server http://<windows-ip>:8420 optimize --pop 32 --steps 500
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import socket
import time
import uuid
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ── 导入优化器 ─────────────────────────────────────────────────────────

import sys

sys.path.insert(0, str(Path(__file__).parent))
from optimize_ratings_gpu import (
    N_PARAMS,
    POSITIONS,
    DIMENSIONS,
    ATTACK_METRICS,
    build_feature_tensors,
    compute_ratings_torch,
    compute_team_avg_ratings,
    load_data,
    optimize,
    _get_default_params_tensor,
    make_holdout_split,
    _filter_by_seasons,
    evaluate_params,
)

from scipy.stats import pearsonr, spearmanr

# ── FastAPI App ──────────────────────────────────────────────────────

app = FastAPI(
    title="ScoutLab GPU Server",
    description="远程 GPU 计算服务 — 球员评分权重优化",
    version="3.0.0",
)

# 全局状态
DATA_DIR: Path = Path("./data")
DEVICE: Optional[torch.device] = None
_cached_df = None
_cached_feat = None
_cached_team_pts = None
_jobs: OrderedDict[str, dict] = OrderedDict()


def _get_device():
    global DEVICE
    if DEVICE is None:
        if torch.cuda.is_available():
            DEVICE = torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            DEVICE = torch.device("mps")
        else:
            DEVICE = torch.device("cpu")
    return DEVICE


def _get_data():
    global _cached_df, _cached_feat, _cached_team_pts
    if _cached_feat is None:
        print("  [cache miss] 加载数据...")
        df, team_pts = load_data(DATA_DIR)
        print(f"  球员: {len(df)}, 球队赛季: {len(team_pts)}")
        _cached_df = df
        _cached_feat = build_feature_tensors(df)
        _cached_team_pts = team_pts
    return _cached_df, _cached_feat, _cached_team_pts


def _invalidate_cache():
    global _cached_df, _cached_feat, _cached_team_pts
    _cached_df = None
    _cached_feat = None
    _cached_team_pts = None


# ── 请求/响应模型 ────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    device: str
    gpu_name: Optional[str] = None
    cuda_available: bool
    mps_available: bool
    data_dir: str
    data_loaded: bool


class OptimizeRequest(BaseModel):
    steps: int = Field(default=500, ge=10, le=5000)
    lr: float = Field(default=0.05, gt=0, le=1.0)
    pop: int = Field(default=32, ge=1, le=256)
    seed: int = Field(default=42)
    test_seasons: int = Field(default=1, ge=1, le=5, description="holdout 使用最近几个赛季")
    min_train_seasons: int = Field(default=2, ge=1, le=10)


class ScoreRequest(BaseModel):
    player_name: str
    team: Optional[str] = None
    league: Optional[str] = None
    season: Optional[str] = None


class ScoreResponse(BaseModel):
    player: str
    score: float
    sub_position: str
    team: str
    league: str
    season: str


class BulkScoreRequest(BaseModel):
    top_n: int = Field(default=50, ge=1, le=500)
    position: Optional[str] = None
    league: Optional[str] = None
    season: Optional[str] = None


class BulkScoreResponse(BaseModel):
    count: int
    players: list[dict]


# ── API 端点 ─────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health():
    dev = _get_device()
    gpu_name = None
    if dev.type == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
    return HealthResponse(
        device=str(dev),
        gpu_name=gpu_name,
        cuda_available=torch.cuda.is_available(),
        mps_available=getattr(torch.backends, "mps", None) is not None
        and torch.backends.mps.is_available(),
        data_dir=str(DATA_DIR.resolve()),
        data_loaded=_cached_feat is not None,
    )


@app.post("/optimize")
async def run_optimize(req: OptimizeRequest):
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"status": "running", "started": time.time()}

    def _run():
        try:
            dev = _get_device()
            df, feat, team_pts = _get_data()

            # Holdout split
            holdout = make_holdout_split(
                df,
                test_seasons=req.test_seasons,
                min_train_seasons=req.min_train_seasons,
            )
            train_df = _filter_by_seasons(df, holdout.train_seasons)
            test_df = _filter_by_seasons(df, holdout.test_seasons)
            train_team_pts = _filter_by_seasons(team_pts, holdout.train_seasons)
            test_team_pts = _filter_by_seasons(team_pts, holdout.test_seasons)
            print(f"  train seasons: {list(holdout.train_seasons)}")
            print(f"  test seasons:  {list(holdout.test_seasons)}")
            print(f"  train players={len(train_df)}, test players={len(test_df)}")

            # Baseline on holdout test set
            default_params = _get_default_params_tensor(dev)
            baseline_test = evaluate_params(
                default_params, test_df, test_team_pts, train_df, dev,
                split_name="test",
            )
            sp_b = baseline_test["metrics"]["spearman"]
            pr_b = baseline_test["metrics"]["pearson"]

            # Optimize on train set only
            train_feat = build_feature_tensors(train_df)
            t0 = time.time()
            best_params = optimize(
                train_feat,
                train_team_pts,
                dev,
                n_steps=req.steps,
                lr=req.lr,
                pop_size=req.pop,
                seed=req.seed,
            )
            elapsed = time.time() - t0

            # Evaluate optimized params on both train and test
            opt_train = evaluate_params(
                best_params, train_df, train_team_pts, train_df, dev,
                split_name="train",
            )
            opt_test = evaluate_params(
                best_params, test_df, test_team_pts, train_df, dev,
                split_name="test",
            )
            sp_opt = opt_test["metrics"]["spearman"]
            pr_opt = opt_test["metrics"]["pearson"]
            overfit_gap = (
                opt_test["metrics"]["rank_loss"] - opt_train["metrics"]["rank_loss"]
            )

            # Per-league on test set
            test_matched = opt_test["matched"]
            per_league = {}
            for league in sorted(test_matched["league"].unique()):
                lm = test_matched[test_matched["league"] == league]
                if len(lm) >= 5:
                    s, _ = spearmanr(lm["pred_rating"], lm["actual_points"])
                    p, _ = pearsonr(lm["pred_rating"], lm["actual_points"])
                    per_league[league] = {
                        "spearman": round(float(s), 4),
                        "pearson": round(float(p), 4),
                        "n": int(len(lm)),
                    }

            # Position weights (with caps applied)
            from optimize_ratings_gpu import apply_position_weight_caps, N_POS as _N_POS, N_DIM as _N_DIM, N_ATK as _N_ATK
            pw_raw = best_params[: _N_POS * _N_DIM].reshape(_N_POS, _N_DIM)
            pw = apply_position_weight_caps(torch.softmax(pw_raw, dim=1)).cpu().numpy()
            position_weights = {}
            for i, pos in enumerate(POSITIONS):
                position_weights[pos] = {
                    dim: round(float(pw[i, j]), 4)
                    for j, dim in enumerate(DIMENSIONS)
                }

            aw_raw = best_params[_N_POS * _N_DIM : _N_POS * _N_DIM + _N_ATK * _N_POS].reshape(
                _N_POS, _N_ATK
            )
            aw = torch.softmax(aw_raw, dim=1).cpu().numpy()
            attack_weights = {}
            for i, pos in enumerate(POSITIONS):
                attack_weights[pos] = {
                    m: round(float(aw[i, j]), 4) for j, m in enumerate(ATTACK_METRICS)
                }

            # Params as base64
            buf = io.BytesIO()
            np.save(buf, best_params.cpu().numpy(), allow_pickle=False)
            params_b64 = base64.b64encode(buf.getvalue()).decode()

            result = {
                "status": "ok",
                # Holdout test metrics (the real numbers)
                "spearman": round(float(sp_opt), 4),
                "pearson": round(float(pr_opt), 4),
                "baseline_spearman": round(float(sp_b), 4),
                "baseline_pearson": round(float(pr_b), 4),
                "spearman_improvement": round(float(sp_opt - sp_b), 4),
                "pearson_improvement": round(float(pr_opt - pr_b), 4),
                # Train metrics (for overfitting check)
                "train_spearman": round(float(opt_train["metrics"]["spearman"]), 4),
                "train_pearson": round(float(opt_train["metrics"]["pearson"]), 4),
                "overfit_rank_loss_gap": round(float(overfit_gap), 4),
                # Split info
                "train_seasons": list(holdout.train_seasons),
                "test_seasons": list(holdout.test_seasons),
                "n_players": int(len(df)),
                "n_train_players": int(len(train_df)),
                "n_test_players": int(len(test_df)),
                "n_team_seasons": int(opt_test["metrics"]["n_team_seasons"]),
                "device": str(dev),
                "elapsed_seconds": round(elapsed, 1),
                "params_base64": params_b64,
                "position_weights": position_weights,
                "attack_weights": attack_weights,
                "per_league": per_league,
            }
            _jobs[job_id] = {"status": "done", "result": result}
            print(f"  Job {job_id} done: test Spearman={sp_opt:.4f} train Spearman={opt_train['metrics']['spearman']:.4f}")
        except Exception as e:
            import traceback

            tb = traceback.format_exc()
            print(f"  Job {job_id} ERROR: {e}\n{tb}")
            _jobs[job_id] = {"status": "error", "error": str(e), "traceback": tb}

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run)
    return {"job_id": job_id, "status": "started"}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in _jobs:
        return JSONResponse(status_code=404, content={"error": "任务不存在"})
    return _jobs[job_id]


@app.post("/score", response_model=ScoreResponse)
async def score_player(req: ScoreRequest):
    dev = _get_device()
    _, feat, _ = _get_data()
    df = feat["df"]

    mask = df["player"].str.contains(req.player_name, case=False, na=False)
    if req.team:
        mask &= df["team"].str.contains(req.team, case=False, na=False)
    if req.league:
        mask &= df["league"].str.contains(req.league, case=False, na=False)
    if req.season:
        mask &= df["season"].astype(str).str.contains(req.season, na=False)

    if mask.sum() == 0:
        return JSONResponse(
            status_code=404, content={"error": f"未找到球员: {req.player_name}"}
        )

    sub = df[mask].sort_values("minutes", ascending=False).iloc[0]
    idx = df.index.get_loc(sub.name) if hasattr(sub, "name") else 0

    params_path = DATA_DIR / "gold" / "feature_store" / "optimized_params.npy"
    if params_path.exists():
        params = torch.tensor(np.load(params_path), dtype=torch.float32, device=dev)
    else:
        params = _get_default_params_tensor(dev)

    ratings = compute_ratings_torch(feat, params, dev)
    score = float(ratings[idx].item())

    return ScoreResponse(
        player=str(sub["player"]),
        score=round(score, 1),
        sub_position=str(sub["sub_position"]),
        team=str(sub["team"]),
        league=str(sub["league"]),
        season=str(sub["season"]),
    )


@app.post("/scores/bulk", response_model=BulkScoreResponse)
async def bulk_scores(req: BulkScoreRequest):
    dev = _get_device()
    _, feat, _ = _get_data()
    df = feat["df"]

    mask = np.ones(len(df), dtype=bool)
    if req.position:
        pos_upper = req.position.upper()
        mask &= df["sub_position"].values == pos_upper
    if req.league:
        mask &= df["league"].str.contains(req.league, case=False, na=False).values
    if req.season:
        mask &= df["season"].astype(str).str.contains(req.season, na=False).values

    if mask.sum() == 0:
        return BulkScoreResponse(count=0, players=[])

    sub_df = df[mask].copy()

    params_path = DATA_DIR / "gold" / "feature_store" / "optimized_params.npy"
    if params_path.exists():
        params = torch.tensor(np.load(params_path), dtype=torch.float32, device=dev)
    else:
        params = _get_default_params_tensor(dev)

    ratings = compute_ratings_torch(feat, params, dev)
    sub_df["score"] = ratings[mask].cpu().numpy()
    sub_df = sub_df.sort_values("score", ascending=False).head(req.top_n)

    players = []
    for _, row in sub_df.iterrows():
        players.append(
            {
                "player": str(row["player"]),
                "team": str(row["team"]),
                "league": str(row["league"]),
                "season": str(row["season"]),
                "position": str(row["sub_position"]),
                "score": round(float(row["score"]), 1),
            }
        )

    return BulkScoreResponse(count=len(players), players=players)


@app.post("/upload-data")
async def upload_data(file: UploadFile = File(...)):
    content = await file.read()
    if file.filename.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            zf.extractall(DATA_DIR)
        _invalidate_cache()
        return {"status": "ok", "message": f"已解压 {file.filename} 到 {DATA_DIR}"}
    else:
        target = DATA_DIR / file.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        _invalidate_cache()
        return {"status": "ok", "message": f"已保存 {target}"}


@app.post("/reload-data")
async def reload_data():
    _invalidate_cache()
    _get_data()
    return {"status": "ok", "message": "数据已重新加载"}


# ── 启动 ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="ScoutLab GPU 计算服务器")
    parser.add_argument("--data_dir", type=str, default="./data")
    parser.add_argument("--port", type=int, default=8420)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    global DATA_DIR
    DATA_DIR = Path(args.data_dir).resolve()
    print("=" * 60)
    print("ScoutLab GPU 计算服务器 v3")
    print("=" * 60)
    print(f"  数据目录: {DATA_DIR}")
    print(f"  监听: {args.host}:{args.port}")

    dev = _get_device()
    if dev.type == "cuda":
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
    else:
        print(f"  设备: {dev}")

    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
        print(f"  本机 IP: {local_ip}")
    except Exception:
        print(f"  主机名: {hostname}")

    print(f"\n  Mac 端连接: python gpu_client.py --server http://<IP>:{args.port} optimize")
    print("=" * 60)

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
