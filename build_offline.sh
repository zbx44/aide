#!/bin/bash
# ==========================================
#  AIDE 离线部署包制作脚本 v0.3
#  新版目录结构：app/config/data/user分离
#  支持 Windows + Linux 双平台
# ==========================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 读取版本号
VERSION=$(cat VERSION 2>/dev/null || echo "0.3.0")
PKG_NAME="aide-offline-v${VERSION}-$(date +%Y%m%d%H%M)"
PKG_DIR="/tmp/$PKG_NAME"

echo "========================================="
echo "  AIDE 离线部署包制作 v${VERSION}"
echo "========================================="
echo ""

# 创建打包目录
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/aide"

# ===== [1/6] 复制应用代码 =====
echo "[1/6] 复制应用代码 (app/)..."
if [ -d "app" ]; then
    rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' \
        --exclude='.env' --exclude='data' --exclude='static' \
        "app/" "$PKG_DIR/aide/app/"
    echo "  ✅ app/ 已复制"
else
    # 兼容旧版：如果没有app/，用backend/
    echo "  ⚠️ app/ 不存在，使用 backend/ 兼容模式"
    rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' \
        --exclude='.env' --exclude='data' --exclude='static' \
        "backend/" "$PKG_DIR/aide/app/backend/"
fi

# ===== [2/6] 复制配置 =====
echo "[2/6] 复制预置配置 (config/)..."
if [ -d "config" ]; then
    cp -r config/ "$PKG_DIR/aide/config/"
    echo "  ✅ config/ 已复制"
fi

# ===== [3/6] 复制前端构建产物 =====
echo "[3/6] 复制前端构建产物..."
# 新版：app/backend/static/
if [ -d "app/backend/static" ]; then
    mkdir -p "$PKG_DIR/aide/app/backend/static"
    cp -r app/backend/static/* "$PKG_DIR/aide/app/backend/static/" 2>/dev/null || true
    echo "  ✅ app/backend/static/ 已复制"
fi
# 旧版兼容
if [ -d "backend/static" ] && [ ! -d "app/backend/static" ]; then
    mkdir -p "$PKG_DIR/aide/app/backend/static"
    cp -r backend/static/* "$PKG_DIR/aide/app/backend/static/" 2>/dev/null || true
    echo "  ✅ backend/static/ 已复制（兼容模式）"
fi

# ===== [4/6] 复制文档、脚本、桌面客户端 =====
echo "[4/6] 复制文档和脚本..."
cp -r docs/ "$PKG_DIR/aide/docs/" 2>/dev/null || true
cp README.md "$PKG_DIR/aide/README.md" 2>/dev/null || true
cp VERSION "$PKG_DIR/aide/VERSION"
cp migrate.py "$PKG_DIR/aide/migrate.py"

# 安装脚本
cp install.sh "$PKG_DIR/aide/install.sh"
cp install.bat "$PKG_DIR/aide/install.bat"

# 启动/停止脚本
cp start.sh "$PKG_DIR/aide/start.sh"
cp stop.sh "$PKG_DIR/aide/stop.sh"
cp start.bat "$PKG_DIR/aide/start.bat"
cp stop.bat "$PKG_DIR/aide/stop.bat"

# 桌面客户端
if [ -d "desktop" ]; then
    mkdir -p "$PKG_DIR/aide/desktop"
    cp desktop/*.py "$PKG_DIR/aide/desktop/" 2>/dev/null || true
    cp desktop/requirements.txt "$PKG_DIR/aide/desktop/requirements.txt" 2>/dev/null || true
    echo "  ✅ desktop/ 已复制"
fi

# ===== [5/6] 生成离线部署脚本 =====
echo "[5/6] 生成离线部署脚本..."

# --- Linux 离线部署脚本 ---
cat > "$PKG_DIR/aide/setup_offline.sh" << 'SETUPEOF'
#!/bin/bash
# ==========================================
#  AIDE 智能助手 - Linux离线部署
#  新版目录结构：代码/配置/数据/用户分离
# ==========================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "  AIDE 智能助手 - Linux离线部署"
echo "========================================="
echo ""

# 检查Python3
if ! command -v python3 &>/dev/null; then
    echo "[错误] 未找到python3，请先安装: sudo apt install python3 python3-venv"
    exit 1
fi

# 虚拟环境
BACKEND_DIR="$SCRIPT_DIR/app/backend"
if [ -d "$BACKEND_DIR/venv" ]; then
    echo "[信息] 虚拟环境已存在"
else
    echo "[1/3] 创建虚拟环境..."
    python3 -m venv "$BACKEND_DIR/venv" || {
        sudo apt install -y python3-venv 2>/dev/null
        python3 -m venv "$BACKEND_DIR/venv"
    }
fi

source "$BACKEND_DIR/venv/bin/activate"

# 安装依赖
echo "[2/3] 安装依赖..."
if [ -d "$SCRIPT_DIR/pip_cache" ]; then
    pip install --no-index --find-links="$SCRIPT_DIR/pip_cache" -r "$BACKEND_DIR/requirements.txt" 2>/dev/null || \
    pip install -r "$BACKEND_DIR/requirements.txt" -q
else
    pip install -r "$BACKEND_DIR/requirements.txt" -q
fi

# 初始化用户目录
echo "[3/3] 初始化用户目录..."
mkdir -p data user/tasks user/templates output logs

if [ ! -f "user/user.env" ]; then
    cat > user/user.env << 'ENVEOF'
# AIDE 用户自定义配置
# 此文件优先级高于 config/default.env
# 升级时不会被覆盖
ENVEOF
fi

# 生成启动脚本
cat > start.sh << 'STARTEOF'
#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AIDE_ROOT="$SCRIPT_DIR"
mkdir -p "$SCRIPT_DIR/data" "$SCRIPT_DIR/user" "$SCRIPT_DIR/output" "$SCRIPT_DIR/logs"
cd "$SCRIPT_DIR/app/backend"
source venv/bin/activate
echo "[AIDE] 启动中... 访问 http://localhost:8900"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8900
STARTEOF
chmod +x start.sh

cat > stop.sh << 'STOPEOF'
#!/bin/bash
pkill -f "uvicorn main:app.*8900" 2>/dev/null && echo "[AIDE] 已停止" || echo "[AIDE] 未找到运行中的服务"
STOPEOF
chmod +x stop.sh

echo ""
echo "========================================="
echo "  部署完成！"
echo "========================================="
echo ""
echo "  启动: ./start.sh"
echo "  停止: ./stop.sh"
echo "  访问: http://$(hostname -I | awk '{print $1}'):8900"
echo ""
echo "  📂 目录说明："
echo "    app/     - 程序代码（升级时覆盖）"
echo "    config/  - 默认配置（升级时覆盖）"
echo "    data/    - 你的数据（升级不碰）"
echo "    user/    - 你的配置和模板（升级不碰）"
echo "    output/  - 生成的文档（升级不碰）"
echo ""
SETUPEOF
chmod +x "$PKG_DIR/aide/setup_offline.sh"

# --- Windows 离线部署说明 ---
cat > "$PKG_DIR/aide/WINDOWS安装说明.txt" << 'WINEOF'
========================================
  AIDE 智能助手 - Windows离线安装说明
========================================

1. 双击 install.bat 安装
2. 双击 start.bat 启动
3. 浏览器打开 http://127.0.0.1:8900

目录说明：
  app\     - 程序代码（升级时覆盖）
  config\  - 默认配置（升级时覆盖）
  data\    - 你的数据（升级不碰！）
  user\    - 你的配置和模板（升级不碰！）
  output\  - 生成的文档（升级不碰）

修改配置：
  编辑 user\user.env 即可，优先级高于 config\default.env
  升级时 user\user.env 不会被覆盖

使用手册：
  docs\操作手册.md
WINEOF

# ===== [6/6] 导出pip离线包 =====
echo "[6/6] 导出pip离线包..."
mkdir -p "$PKG_DIR/aide/pip_cache"

# 尝试从现有venv导出
if [ -d "app/backend/venv" ]; then
    VENV_DIR="app/backend/venv"
elif [ -d "backend/venv" ]; then
    VENV_DIR="backend/venv"
else
    VENV_DIR=""
fi

if [ -n "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    REQ_FILE="app/backend/requirements.txt"
    [ ! -f "$REQ_FILE" ] && REQ_FILE="backend/requirements.txt"
    
    if [ -f "$REQ_FILE" ]; then
        pip download -r "$REQ_FILE" \
            -d "$PKG_DIR/aide/pip_cache" \
            --platform manylinux2014_x86_64 \
            --python-version 311 \
            --only-binary=:all: 2>/dev/null || {
            echo "  [警告] 部分包无法下载二进制"
        }
        # 同时下载Windows版本
        pip download -r "$REQ_FILE" \
            -d "$PKG_DIR/aide/pip_cache_win" \
            --platform win_amd64 \
            --python-version 38 \
            --only-binary=:all: 2>/dev/null || {
            echo "  [警告] Windows包下载失败，用户需在线安装"
        }
        # 合并
        if [ -d "$PKG_DIR/aide/pip_cache_win" ]; then
            mv "$PKG_DIR/aide/pip_cache_win/"* "$PKG_DIR/aide/pip_cache/" 2>/dev/null || true
            rmdir "$PKG_DIR/aide/pip_cache_win" 2>/dev/null || true
        fi
    fi
fi

PIP_COUNT=$(ls "$PKG_DIR/aide/pip_cache/" 2>/dev/null | wc -l)
echo "  离线包数量: $PIP_COUNT"

# ===== 统计和打包 =====
echo ""
echo "正在打包..."

# 计算文件数
FILE_COUNT=$(find "$PKG_DIR/aide" -type f | wc -l)
echo "  文件数: $FILE_COUNT"

cd "$PKG_DIR"
tar czf "$SCRIPT_DIR/${PKG_NAME}.tar.gz" aide/

SIZE=$(du -h "$SCRIPT_DIR/${PKG_NAME}.tar.gz" | cut -f1)
echo ""
echo "========================================="
echo "  离线包制作完成！"
echo "========================================="
echo ""
echo "  文件: ${PKG_NAME}.tar.gz ($SIZE)"
echo "  版本: v${VERSION}"
echo ""
echo "  Linux部署："
echo "    1. 上传到目标服务器"
echo "    2. tar xzf ${PKG_NAME}.tar.gz"
echo "    3. cd ${PKG_NAME}/aide"
echo "    4. bash setup_offline.sh"
echo "    5. ./start.sh"
echo ""
echo "  Windows部署："
echo "    1. 解压到目标电脑"
echo "    2. 双击 install.bat"
echo "    3. 双击 start.bat"
echo ""

# 清理
rm -rf "$PKG_DIR"
