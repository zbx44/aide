#!/bin/bash
# ==========================================
#  AIDE Win10 离线部署包制作脚本 v0.3
#  在Linux上交叉打包Windows ZIP
# ==========================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VERSION=$(cat VERSION 2>/dev/null || echo "0.3.0")
PKG_NAME="aide-offline-v${VERSION}-win10"
PKG_DIR="/tmp/$PKG_NAME"

echo "========================================="
echo "  AIDE Win10 离线包制作 v${VERSION}"
echo "========================================="
echo ""

rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/aide"

# ===== [1/7] 复制应用代码 =====
echo "[1/7] 复制应用代码 (app/)..."
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' \
    --exclude='.env' --exclude='data' --exclude='static' \
    "app/" "$PKG_DIR/aide/app/"

# 自动转换换行符为CRLF（Windows友好）
find "$PKG_DIR/aide/app" -name "*.py" -exec sed -i 's/$/\r/' {} \;

# ===== [2/7] 复制配置 =====
echo "[2/7] 复制预置配置 (config/)..."
cp -r config/ "$PKG_DIR/aide/config/"

# YAML文件也转CRLF
find "$PKG_DIR/aide/config" -name "*.yaml" -o -name "*.yml" | xargs sed -i 's/$/\r/' 2>/dev/null || true

# ===== [3/7] 复制前端构建产物 =====
echo "[3/7] 复制前端构建产物..."
STATIC_SRC=""
if [ -d "app/backend/static" ]; then
    STATIC_SRC="app/backend/static"
elif [ -d "backend/static" ]; then
    STATIC_SRC="backend/static"
fi

if [ -n "$STATIC_SRC" ]; then
    mkdir -p "$PKG_DIR/aide/app/backend/static"
    cp -r "$STATIC_SRC"/* "$PKG_DIR/aide/app/backend/static/" 2>/dev/null || true
    echo "  ✅ 前端静态文件已复制"
else
    echo "  ⚠️ 无前端构建产物，请先 npm run build"
fi

# ===== [4/7] 复制pip离线包 =====
echo "[4/7] 复制pip离线缓存..."
if [ -d "pip_cache_win10" ] && [ "$(ls -A pip_cache_win10)" ]; then
    cp -r pip_cache_win10/ "$PKG_DIR/aide/pip_cache_win10/"
    CACHE_SIZE=$(du -sh pip_cache_win10/ | cut -f1)
    CACHE_COUNT=$(ls pip_cache_win10/ | wc -l)
    echo "  ✅ pip_cache_win10/ ($CACHE_SIZE, $CACHE_COUNT 个包)"
else
    echo "  ⚠️ pip_cache_win10/ 不存在或为空，依赖需在线安装"
fi

if [ -d "pip_cache_desktop" ] && [ "$(ls -A pip_cache_desktop)" ]; then
    cp -r pip_cache_desktop/ "$PKG_DIR/aide/pip_cache_desktop/"
    CACHE_SIZE=$(du -sh pip_cache_desktop/ | cut -f1)
    echo "  ✅ pip_cache_desktop/ ($CACHE_SIZE, 桌面客户端可选)"
fi

# ===== [5/9] 复制文档、脚本、桌面客户端 =====
echo "[5/9] 复制文档和脚本..."
cp -r docs/ "$PKG_DIR/aide/docs/" 2>/dev/null || true
cp README.md "$PKG_DIR/aide/" 2>/dev/null || true
cp VERSION "$PKG_DIR/aide/"
cp migrate.py "$PKG_DIR/aide/"
cp install.bat "$PKG_DIR/aide/"
cp start.bat "$PKG_DIR/aide/"
cp stop.bat "$PKG_DIR/aide/"

if [ -d "desktop" ]; then
    cp -r desktop/ "$PKG_DIR/aide/desktop/"
    find "$PKG_DIR/aide/desktop" -name "*.py" -exec sed -i 's/$/\r/' {} \;
    echo "  ✅ desktop/ 已复制"
fi

# 如果没有install.sh对应版本也带上
[ -f install.sh ] && cp install.sh "$PKG_DIR/aide/"
[ -f start.sh ] && cp start.sh "$PKG_DIR/aide/"
[ -f stop.sh ] && cp stop.sh "$PKG_DIR/aide/"

# ===== [5/7] 生成Win10专用脚本 =====
echo "[6/9] 生成Win10专用脚本..."

# --- start.bat（自动检测Python）---
cat > "$PKG_DIR/aide/start.bat" << 'BAT_EOF'
@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: 定位项目根目录
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set AIDE_ROOT=%ROOT%

:: ===== 检测Python =====
set "PYTHON_EXE="

:: 优先：内置嵌入版Python
if exist "%ROOT%\python\python.exe" (
    set "PYTHON_EXE=%ROOT%\python\python.exe"
)

:: 其次：项目内venv
if not defined PYTHON_EXE if exist "%ROOT%\app\backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT%\app\backend\venv\Scripts\python.exe"
)

:: 最后：系统Python
if not defined PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%p in ('where python') do set "PYTHON_EXE=%%p"
    )
)

if not defined PYTHON_EXE (
    echo.
    echo [错误] 未找到Python！
    echo.
    echo 解决方案：
    echo   1. 运行 install.bat 自动安装
    echo   2. 或下载Python 3.8+: https://www.python.org/downloads/
    echo      安装时勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo.
echo =========================================
echo   AIDE 智能助手 v0.3
echo =========================================
echo.
echo   Python: %PYTHON_EXE%
"%PYTHON_EXE%" --version
echo.

:: 创建数据目录
if not exist "%ROOT%\data" mkdir "%ROOT%\data"
if not exist "%ROOT%\user" mkdir "%ROOT%\user"
if not exist "%ROOT%\output" mkdir "%ROOT%\output"
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"

:: 启动后端
if exist "%ROOT%\app\backend" (
    cd /d "%ROOT%\app\backend"
) else if exist "%ROOT%\backend" (
    cd /d "%ROOT%\backend"
) else (
    echo [错误] 未找到后端目录
    pause
    exit /b 1
)

echo [AIDE] 启动中... 请稍候
echo [AIDE] 浏览器访问 http://127.0.0.1:8900
echo.
echo [AIDE] 按 Ctrl+C 停止服务
echo.

"%PYTHON_EXE%" -m uvicorn main:app --host 127.0.0.1 --port 8900

pause
BAT_EOF

# --- stop.bat ---
cat > "$PKG_DIR/aide/stop.bat" << 'BAT_EOF'
@echo off
chcp 65001 >nul 2>&1
echo [AIDE] 正在停止服务...
:: 杀掉监听8900端口的进程
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8900 ^| findstr LISTENING') do (
    taskkill /f /pid %%a 2>nul
)
echo [AIDE] 已停止
timeout /t 2 >nul
BAT_EOF

# --- upgrade_offline.bat (U盘升级) ---
cat > "$PKG_DIR/aide/upgrade_offline.bat" << 'BAT_EOF'
@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

echo =========================================
echo   AIDE 离线升级
echo =========================================
echo.

:: 查找升级包
set "UPDATE_ZIP="
for %%f in ("%ROOT%\aide-update-v*.zip") do set "UPDATE_ZIP=%%f"

if not defined UPDATE_ZIP (
    echo [错误] 未找到升级包！
    echo.
    echo 请将升级包 ^(aide-update-vX.X.X.zip^) 复制到：
    echo   %ROOT%\
    echo.
    pause
    exit /b 1
)

echo [信息] 找到升级包: %UPDATE_ZIP%
echo.

:: 确认
set /p CONFIRM="确认升级？(Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo 已取消
    pause
    exit /b 0
)

:: 停止服务
echo [1/4] 停止服务...
call "%ROOT%\stop.bat" 2>nul
timeout /t 3 >nul

:: 备份
set "BACKUP_DIR=%ROOT%\backup\%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%"
set "BACKUP_DIR=%BACKUP_DIR: =0%"
echo [2/4] 备份到 %BACKUP_DIR%...
mkdir "%BACKUP_DIR%" 2>nul
xcopy "%ROOT%\app" "%BACKUP_DIR%\app\" /e /i /q >nul 2>&1
xcopy "%ROOT%\config" "%BACKUP_DIR%\config\" /e /i /q >nul 2>&1

:: 解压升级包
echo [3/4] 解压升级包...
powershell -Command "Expand-Archive -Path '%UPDATE_ZIP%' -DestinationPath '%ROOT%\aide-update-temp' -Force" 2>nul

:: 覆盖app和config（不动data/user/output）
if exist "%ROOT%\aide-update-temp\app" (
    rmdir /s /q "%ROOT%\app" 2>nul
    xcopy "%ROOT%\aide-update-temp\app" "%ROOT%\app\" /e /i /q >nul 2>&1
)
if exist "%ROOT%\aide-update-temp\config" (
    :: 合并配置：保留user修改的default.env不变，只更新新增项
    xcopy "%ROOT%\aide-update-temp\config" "%ROOT%\config\" /e /i /q /d >nul 2>&1
)

:: 清理
rmdir /s /q "%ROOT%\aide-update-temp" 2>nul

:: 运行迁移
echo [4/4] 运行数据迁移...
if exist "%ROOT%\app\backend" (
    cd /d "%ROOT%\app\backend"
) else (
    cd /d "%ROOT%\backend"
)
if defined PYTHON_EXE (
    "%PYTHON_EXE%" -c "from core.migrations import MigrationRunner; MigrationRunner('%ROOT%').run_pending()" 2>nul
)

echo.
echo =========================================
echo   升级完成！双击 start.bat 启动
echo =========================================
echo.
pause
BAT_EOF

# 所有.bat文件转CRLF
find "$PKG_DIR/aide" -name "*.bat" -exec sed -i 's/$/\r/' {} \;
find "$PKG_DIR/aide" -name "*.txt" -exec sed -i 's/$/\r/' {} \;
find "$PKG_DIR/aide" -name "*.md" -exec sed -i 's/$/\r/' {} \;
find "$PKG_DIR/aide" -name "*.env" -exec sed -i 's/$/\r/' {} \;

# ===== [6/7] Windows部署说明 =====
echo "[7/9] 生成部署说明..."

cat > "$PKG_DIR/aide/WINDOWS部署说明.txt" << 'DOCEOF'
========================================
  AIDE 智能助手 v0.3 - Win10 部署指南
========================================

【快速开始】
  1. 双击 install.bat（首次安装）
  2. 双击 start.bat（启动服务）
  3. 浏览器打开 http://127.0.0.1:8900

【桌面客户端】
  双击 start_desktop.bat（带系统托盘图标）

【离线升级】
  1. 将升级包(aide-update-vX.X.X.zip)复制到本项目根目录
  2. 双击 upgrade_offline.bat

【目录说明】
  app\      - 程序代码（升级时覆盖）
  config\   - 默认配置（升级时覆盖）
  data\     - 你的数据（升级不碰！）
  user\     - 你的配置和模板（升级不碰！）
  output\   - 生成的文档（升级不碰）
  logs\     - 运行日志
  python\   - 嵌入式Python（可选）
  backup\   - 升级备份

【修改配置】
  编辑 user\user.env，优先级高于 config\default.env
  升级时 user\user.env 不会被覆盖

【使用手册】
  docs\操作手册.md

【联系支持】
  数字化转型部
DOCEOF

sed -i 's/$/\r/' "$PKG_DIR/aide/WINDOWS部署说明.txt"

# ===== [7/7] 打ZIP包 =====
echo "[8/9] 准备达梦驱动说明..."

# dmPython 不能通过pip安装，需要在目标机器手动安装
cat > "$PKG_DIR/aide/达梦数据库驱动安装说明.txt" << 'DMEOF'
========================================
  达梦数据库驱动 dmPython 安装说明
========================================

AIDE的Text2SQL功能需要连接达梦数据库，需安装dmPython驱动。

【安装步骤】
1. 从达梦安装目录找到dmPython安装包：
   通常在 /dmdbms/drivers/python/dmPython/

2. 根据Python版本选择对应的whl文件：
   Python 3.8 → dmPython-cp38-win_amd64.whl

3. 安装：
   pip install dmPython-cp38-win_amd64.whl

4. 验证：
   python -c "import dmPython; print('OK')"

【注意】
- dmPython与达梦数据库版本强关联，请使用同版本驱动
- 如果不使用Text2SQL查询达梦数据库的功能，可以跳过此步骤
- 其他功能（AI对话、文档生成、模板系统）不受影响
DMEOF

# 所有.txt文件转CRLF
find "$PKG_DIR/aide" -name "*.txt" -exec sed -i 's/$/\r/' {} \;

echo "[9/9] 打包ZIP..."

rm -f "$SCRIPT_DIR"/aide-offline-*-win10.zip

cd "$PKG_DIR"
zip -r -q "$SCRIPT_DIR/${PKG_NAME}.zip" aide/

SIZE=$(du -h "$SCRIPT_DIR/${PKG_NAME}.zip" | cut -f1)
FILE_COUNT=$(find "$PKG_DIR" -type f | wc -l)

# 清理
rm -rf "$PKG_DIR"

echo ""
echo "========================================="
echo "  Win10 离线包制作完成！"
echo "========================================="
echo ""
echo "  文件: ${PKG_NAME}.zip ($SIZE)"
echo "  版本: v${VERSION}"
echo "  文件: ${FILE_COUNT} 个"
echo ""
echo "  部署步骤:"
echo "    1. 复制到目标Win10电脑"
echo "    2. 右键 → 全部解压"
echo "    3. 进入 aide 文件夹"
echo "    4. 双击 install.bat"
echo "    5. 双击 start.bat"
echo ""
