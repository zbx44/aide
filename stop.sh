#!/bin/bash
# AIDE 智能助手 - 停止脚本
pkill -f "uvicorn main:app.*8900" 2>/dev/null && echo "[AIDE] 已停止" || echo "[AIDE] 未找到运行中的服务"
