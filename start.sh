#!/bin/bash
# ScoutFootball 统一启动脚本
# 支持启动 Streamlit 或 FastAPI+Liquid Glass 前端

echo "=========================================="
echo "  ScoutFootball 分析平台"
echo "=========================================="
echo ""
echo "请选择要启动的服务:"
echo ""
echo "  1. Streamlit 前端 (12个页面，含世界杯功能)"
echo "  2. FastAPI + Liquid Glass 前端 (API服务+静态页面)"
echo "  3. 两者都启动 (Streamlit 8501, API 8000)"
echo ""
read -p "请输入选项 (1/2/3): " choice

case $choice in
    1)
        echo ""
        echo "正在启动 Streamlit 前端..."
        echo ""
        uv run streamlit run src/scoutfootball/app/streamlit_app.py
        ;;
    2)
        echo ""
        echo "正在启动 FastAPI 服务器 (端口 8000)..."
        echo "访问 http://localhost:8000 查看 Liquid Glass 前端"
        echo "API 文档: http://localhost:8000/docs"
        echo ""
        uv run python -m scoutfootball serve
        ;;
    3)
        echo ""
        echo "正在同时启动两个服务..."
        echo "  - Streamlit: http://localhost:8501"
        echo "  - FastAPI/Liquid Glass: http://localhost:8000"
        echo ""
        uv run streamlit run src/scoutfootball/app/streamlit_app.py &
        STREAMLIT_PID=$!
        sleep 3
        echo "启动 FastAPI 服务器..."
        uv run python -m scoutfootball serve &
        API_PID=$!
        wait $STREAMLIT_PID $API_PID
        ;;
    *)
        echo "无效选项"
        ;;
esac
