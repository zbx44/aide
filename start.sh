#!/bin/bash
# AIDE 智能助手 - 启动脚本
# 自动检测项目根目录，支持新旧目录结构
set -e

# 检测项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AIDE_ROOT="$SCRIPT_DIR"

# 检查新目录结构是否存在
if [ -d "$SCRIPT_DIR/app/backend" ]; then
    # 新版目录结构
    BACKEND_DIR="$SCRIPT_DIR/app/backend"
    echo "[AIDE] 使用新版目录结构"
    echo "[AIDE] 根目录: $SCRIPT_DIR"
    echo "[AIDE] 数据目录: $SCRIPT_DIR/data"
else
    # 旧版兼容
    BACKEND_DIR="$SCRIPT_DIR/backend"
    echo "[AIDE] 使用旧版目录结构（兼容模式）"
fi

# 检查虚拟环境
if [ -d "$BACKEND_DIR/venv" ]; then
    source "$BACKEND_DIR/venv/bin/activate"
elif [ -d "$SCRIPT_DIR/venv" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# 创建必要目录
mkdir -p "$SCRIPT_DIR/data" "$SCRIPT_DIR/user" "$SCRIPT_DIR/output" "$SCRIPT_DIR/logs"

# 启动
cd "$BACKEND_DIR"
echo "[AIDE] 启动中..."
python3 -m uvicorn main:app --host 0.0.0.0 --port 8900
