#!/bin/bash
# ==========================================
#  AI助手 AIDE v0.3 - Ubuntu 24.04 安装脚本
#  新版目录结构：代码/配置/数据/用户分离
# ==========================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "  AI助手 AIDE v0.3 - Ubuntu 24.04 安装"
echo "========================================="
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ===== 步骤1: 检查系统 =====
info "[1/6] 检查系统环境..."
if ! command -v python3 &>/dev/null; then
    warn "未找到python3，正在安装..."
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-pip python3-venv
fi

PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
info "Python版本: $PYVER"

# ===== 步骤2: 创建虚拟环境 =====
info "[2/6] 创建Python虚拟环境..."

# 新版目录结构
BACKEND_DIR="$SCRIPT_DIR/app/backend"
if [ ! -d "$BACKEND_DIR" ]; then
    # 兼容旧版
    BACKEND_DIR="$SCRIPT_DIR/backend"
fi

if [ -d "$BACKEND_DIR/venv" ]; then
    info "虚拟环境已存在，跳过"
else
    python3 -m venv "$BACKEND_DIR/venv"
    info "虚拟环境创建成功"
fi

source "$BACKEND_DIR/venv/bin/activate"
pip install --upgrade pip -q 2>/dev/null || true

# ===== 步骤3: 安装后端依赖 =====
info "[3/6] 安装后端依赖..."
cd "$BACKEND_DIR"

if [ -f "requirements.txt" ]; then
    if [ -d "$SCRIPT_DIR/packages" ] && [ "$(ls -A "$SCRIPT_DIR/packages" 2>/dev/null)" ]; then
        info "从本地packages目录安装..."
        pip install --no-index --find-links="$SCRIPT_DIR/packages" -r requirements.txt 2>/dev/null || \
        pip install -r requirements.txt -q
    else
        pip install -r requirements.txt -q
    fi
    info "后端依赖安装完成"
fi

cd "$SCRIPT_DIR"

# ===== 步骤4: 安装前端 =====
info "[4/6] 安装前端依赖..."
if [ -d "frontend" ]; then
    if command -v npm &>/dev/null; then
        cd frontend
        npm install --registry=https://registry.npmmirror.com 2>/dev/null || true
        npm run build 2>/dev/null || warn "前端构建失败，可后续手动构建"
        cd "$SCRIPT_DIR"
        # 将构建产物复制到app/backend/static
        if [ -d "frontend/dist" ] && [ -d "app/backend" ]; then
            mkdir -p app/backend/static
            cp -r frontend/dist/* app/backend/static/ 2>/dev/null || true
        fi
    else
        warn "未找到npm，跳过前端构建"
    fi
fi

# ===== 步骤5: 创建用户目录和配置 =====
info "[5/6] 初始化用户数据目录..."

# 创建用户数据目录（不碰已有数据）
mkdir -p data user/tasks user/templates output logs

# 用户配置（只创建不覆盖）
if [ ! -f "user/user.env" ]; then
    cat > user/user.env << 'ENVEOF'
# AIDE 智能助手 - 用户自定义配置
# 此文件优先级高于 config/default.env
# 升级时不会被覆盖，请放心修改
#
# 用法：只需写你想覆盖的配置项，例如：
# LLM_PROVIDER=tencent
# LLM_TENCENT_API_KEY=你的Key
ENVEOF
    info "已创建 user/user.env"
else
    info "user/user.env 已存在，跳过"
fi

# ===== 步骤6: 生成启动脚本 =====
info "[6/6] 生成启动脚本..."

cat > start.sh << 'STARTEOF'
#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AIDE_ROOT="$SCRIPT_DIR"

if [ -d "$SCRIPT_DIR/app/backend" ]; then
    BACKEND_DIR="$SCRIPT_DIR/app/backend"
else
    BACKEND_DIR="$SCRIPT_DIR/backend"
fi

mkdir -p "$SCRIPT_DIR/data" "$SCRIPT_DIR/user" "$SCRIPT_DIR/output" "$SCRIPT_DIR/logs"

if [ -d "$BACKEND_DIR/venv" ]; then
    source "$BACKEND_DIR/venv/bin/activate"
fi

cd "$BACKEND_DIR"
echo "[AIDE] 启动中... 访问 http://localhost:8900"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8900
STARTEOF
chmod +x start.sh

cat > stop.sh << 'STOPEOF'
#!/bin/bash
pkill -f "uvicorn main:app.*8900" 2>/dev/null && echo "[AIDE] 已停止" || echo "[AIDE] 未找到运行中的服务"
STOPEOF
chmod +x stop.sh

# 生成systemd服务文件
cat > aide.service << SVCEOF
[Unit]
Description=AIDE AI Assistant
After=network.target

[Service]
Type=simple
User=$USER
Environment=AIDE_ROOT=$SCRIPT_DIR
WorkingDirectory=$SCRIPT_DIR/app/backend
ExecStart=$SCRIPT_DIR/app/backend/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8900
Restart=on-failure
RestartSec=5
Environment=PATH=$SCRIPT_DIR/app/backend/venv/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
SVCEOF

echo ""
echo "========================================="
echo "  安装完成！"
echo "========================================="
echo ""
echo "启动方式："
echo "  方式1: ./start.sh"
echo "  方式2: sudo cp aide.service /etc/systemd/system/ && sudo systemctl enable --now aide"
echo ""
echo "停止服务: ./stop.sh"
echo ""
echo "浏览器访问: http://$(hostname -I | awk '{print $1}'):8900"
echo ""
echo "📂 目录说明："
echo "  app/     - 程序代码（升级时覆盖）"
echo "  config/  - 默认配置（升级时覆盖）"
echo "  data/    - 你的数据（升级不碰）"
echo "  user/    - 你的配置和模板（升级不碰）"
echo "  output/  - 生成的文档（升级不碰）"
echo ""
echo "💡 如需修改配置，编辑 user/user.env 即可"
echo "📖 使用手册: docs/操作手册.md"
echo ""
