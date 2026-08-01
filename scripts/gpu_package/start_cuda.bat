@echo off
chcp 65001 >nul 2>&1
title ScoutLab GPU Server (CUDA)

echo ============================================================
echo   ScoutLab GPU 计算服务器 — CUDA 专用启动
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python
    pause
    exit /b 1
)

echo [1/2] 检查 CUDA...
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'; print(f'  GPU: {torch.cuda.get_device_name(0)}')"
if errorlevel 1 (
    echo [错误] CUDA 不可用，请确认:
    echo   1. 已安装 NVIDIA 驱动
    echo   2. pip install torch --index-url https://download.pytorch.org/whl/cu124
    pause
    exit /b 1
)

echo.
echo [2/2] 启动服务器...
echo.
python gpu_server.py --data_dir ./data --port 8420
pause
