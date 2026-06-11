# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for ScoutFootball backend server

import sys
from pathlib import Path

block_cipher = None

# Project root (parent of desktop/)
project_root = Path(SPECPATH).parents[0]
src_dir = project_root / "src"

a = Analysis(
    [str(Path(SPECPATH) / "backend" / "server.py")],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "scoutfootball",
        "scoutfootball.api",
        "scoutfootball.api_server",
        "scoutfootball.app.data_loader",
        "scoutfootball.app.demo_data",
        "scoutfootball.config",
        "scoutfootball.evaluation.backtests",
        "scoutfootball.evaluation.calibration",
        "scoutfootball.evaluation.confidence",
        "scoutfootball.evaluation.coverage_confidence",
        "scoutfootball.evaluation.position_metrics",
        "scoutfootball.evaluation.scouting_queue",
        "scoutfootball.evaluation.truth_labels",
        "scoutfootball.models.match_prediction",
        "scoutfootball.models.player_rating_nn",
        "scoutfootball.models.value_fairness",
        "scoutfootball.storage.parquet_io",
        "scoutfootball.storage.duckdb_io",
        "scoutfootball.storage.layout",
        "scoutfootball.worldcup.data",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "pydantic",
        "duckdb",
        "scipy",
        "scipy.optimize",
        "scipy.stats",
        "scipy.stats.qmc",
        "sklearn",
        "sklearn.neural_network",
        "sklearn.isotonic",
        "sklearn.compose",
        "sklearn.impute",
        "sklearn.pipeline",
        "sklearn.preprocessing",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "torch",
        "torchvision",
        "IPython",
        "jupyter",
        "notebook",
        "plotly",
        "PIL",
        "Pillow",
        "altair",
        "lxml",
        "mplsoccer",
        "pyarrow",
        "streamlit",
        "watchdog",
        "tornado",
        "ipykernel",
        "ipywidgets",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="scoutfootball-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="scoutfootball-server",
)
