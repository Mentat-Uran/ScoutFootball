@echo off
REM ScoutFootball 统一启动脚本
REM 支持启动 Streamlit 或 FastAPI+Liquid Glass 前端

echo ==========================================
echo   ScoutFootball 分析平台
echo ==========================================
echo.
echo 请选择要启动的服务:
echo.
echo   1. Streamlit 前端 (12个页面，含世界杯功能)
echo   2. FastAPI + Liquid Glass 前端 (API服务+静态页面)
echo   3. 两者都启动 (Streamlit 8501, API 8000)
echo.
set /p choice="请输入选项 (1/2/3): "

if "%choice%"=="1" goto streamlit
if "%choice%"=="2" goto api
if "%choice%"=="3" goto both

echo 无效选项
goto end

:streamlit
echo.
echo 正在启动 Streamlit 前端...
echo.
uv run streamlit run src/scoutfootball/app/streamlit_app.py
goto end

:api
echo.
echo 正在启动 FastAPI 服务器 (端口 8000)...
echo 访问 http://localhost:8000 查看 Liquid Glass 前端
echo API 文档: http://localhost:8000/docs
echo.
uv run python -m scoutfootball serve
goto end

:both
echo.
echo 正在同时启动两个服务...
echo   - Streamlit: http://localhost:8501
echo   - FastAPI/Liquid Glass: http://localhost:8000
echo.
start "Streamlit" cmd /k "uv run streamlit run src/scoutfootball/app/streamlit_app.py"
timeout /t 2 /nobreak >nul
echo 启动 FastAPI 服务器...
uv run python -m scoutfootball serve
goto end

:end
echo.
