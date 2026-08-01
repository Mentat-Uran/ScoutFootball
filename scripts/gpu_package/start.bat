@echo off
chcp 65001 >nul 2>&1
title ScoutLab GPU Server

echo ============================================================
echo   ScoutLab GPU 计算服务器
echo ============================================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.11+
    echo   下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查依赖
echo [1/2] 检查依赖...
python -c "import torch" >nul 2>&1
if errorlevel 1 (
    echo   首次运行，安装依赖 (需要几分钟)...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
) else (
    echo   依赖已就绪
)

echo.
echo [2/2] 启动服务器...
echo.
python gpu_server.py --data_dir ./data --port 8420
pause
