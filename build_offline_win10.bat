@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ==========================================
::  AIDE Win10 离线部署包制作脚本 v0.3
::  产出：aide-offline-vX.X.X-win10.zip
:: ==========================================

echo =========================================
echo   AIDE Win10 离线包制作 v0.3
echo =========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
cd /d "%SCRIPT_DIR%"

:: 读取版本号
set "VERSION=0.3.0"
if exist VERSION (
    set /p VERSION=<VERSION
)

set "PKG_NAME=aide-offline-v%VERSION%-win10"
set "PKG_DIR=%TEMP%\%PKG_NAME%"

:: 创建打包目录
if exist "%PKG_DIR%" rmdir /s /q "%PKG_DIR%"
mkdir "%PKG_DIR%\aide"

:: ===== [1/8] 复制应用代码 =====
echo [1/8] 复制应用代码 ^(app/^)...
if exist "app" (
    xcopy "app" "%PKG_DIR%\aide\app\" /e /i /q /exclude:%SCRIPT_DIR%\build_exclude.txt >nul 2>&1
    if errorlevel 1 (
        robocopy "app" "%PKG_DIR%\aide\app" /e /xf __pycache__ *.pyc .env /xd venv data .git /njh /njs /np >nul 2>&1
    )
    echo   OK app\
) else if exist "backend" (
    echo   [兼容] 使用 backend\ 目录
    xcopy "backend" "%PKG_DIR%\aide\app\backend\" /e /i /q >nul 2>&1
    echo   OK app\backend\
)

:: ===== [2/8] 复制配置 =====
echo [2/8] 复制预置配置 ^(config/^)...
if exist "config" (
    xcopy "config" "%PKG_DIR%\aide\config\" /e /i /q >nul 2>&1
    echo   OK config\
)

:: ===== [3/8] 复制前端构建产物 =====
echo [3/8] 复制前端构建产物...
if exist "app\backend\static" (
    xcopy "app\backend\static" "%PKG_DIR%\aide\app\backend\static\" /e /i /q >nul 2>&1
    echo   OK app\backend\static\
) else if exist "backend\static" (
    xcopy "backend\static" "%PKG_DIR%\aide\app\backend\static\" /e /i /q >nul 2>&1
    echo   OK backend\static\ ^(兼容^)
)

:: ===== [4/8] 复制文档和脚本 =====
echo [4/8] 复制文档和脚本...
if exist "docs" xcopy "docs" "%PKG_DIR%\aide\docs\" /e /i /q >nul 2>&1
copy /y "README.md" "%PKG_DIR%\aide\" >nul 2>&1
copy /y "VERSION" "%PKG_DIR%\aide\" >nul 2>&1
copy /y "migrate.py" "%PKG_DIR%\aide\" >nul 2>&1
copy /y "install.bat" "%PKG_DIR%\aide\" >nul 2>&1
copy /y "start.bat" "%PKG_DIR%\aide\" >nul 2>&1
copy /y "stop.bat" "%PKG_DIR%\aide\" >nul 2>&1
echo   OK docs + scripts

:: ===== [5/8] 桌面客户端 =====
echo [5/8] 桌面客户端...
if exist "desktop" (
    xcopy "desktop" "%PKG_DIR%\aide\desktop\" /e /i /q >nul 2>&1
    echo   OK desktop\
)

:: ===== [6/8] 生成Win10专用启动脚本 =====
echo [6/8] 生成Win10专用脚本...

:: --- 一键启动（自动检测Python） ---
> "%PKG_DIR%\aide\start.bat" (
    echo @echo off
    echo chcp 65001 ^>nul 2^>^&1
    echo setlocal enabledelayedexpansion
    echo.
    echo :: ===== 定位项目根目录 =====
    echo set "ROOT=%%~dp0"
    echo set "ROOT=%%ROOT:~0,-1%%"
    echo set AIDE_ROOT=%%ROOT%%
    echo.
    echo :: ===== 检测Python =====
    echo set "PYTHON_EXE="
    echo.
    echo :: 优先：内置嵌入版Python
    echo if exist "%%ROOT%%\python\python.exe" ^(
    echo     set "PYTHON_EXE=%%ROOT%%\python\python.exe"
    echo ^)
    echo.
    echo :: 其次：项目内Python安装
    echo if not defined PYTHON_EXE if exist "%%ROOT%%\app\backend\venv\Scripts\python.exe" ^(
    echo     set "PYTHON_EXE=%%ROOT%%\app\backend\venv\Scripts\python.exe"
    echo ^)
    echo.
    echo :: 最后：系统Python
    echo if not defined PYTHON_EXE ^(
    echo     where python >nul 2^>^&1
    echo     if not errorlevel 1 ^(
    echo         for /f "delims=" %%p in ^('where python'^) do set "PYTHON_EXE=%%p"
    echo     ^)
    echo ^)
    echo.
    echo if not defined PYTHON_EXE ^(
    echo     echo [错误] 未找到Python，请先运行 install.bat
    echo     pause
    echo     exit /b 1
    echo ^)
    echo.
    echo echo [AIDE] Python: %%PYTHON_EXE%%
    echo "%%PYTHON_EXE%%" --version
    echo.
    echo :: ===== 创建数据目录 =====
    echo if not exist "%%ROOT%%\data" mkdir "%%ROOT%%\data"
    echo if not exist "%%ROOT%%\user" mkdir "%%ROOT%%\user"
    echo if not exist "%%ROOT%%\output" mkdir "%%ROOT%%\output"
    echo if not exist "%%ROOT%%\logs" mkdir "%%ROOT%%\logs"
    echo.
    echo :: ===== 启动后端 =====
    echo if exist "%%ROOT%%\app\backend" ^(
    echo     cd /d "%%ROOT%%\app\backend"
    echo ^) else if exist "%%ROOT%%\backend" ^(
    echo     cd /d "%%ROOT%%\backend"
    echo ^)
    echo.
    echo echo [AIDE] 启动中... 请稍候
    echo echo [AIDE] 浏览器访问 http://127.0.0.1:8900
    echo echo.
    echo "%%PYTHON_EXE%%" -m uvicorn main:app --host 127.0.0.1 --port 8900
    echo.
    echo pause
)

:: --- 停止脚本 ---
> "%PKG_DIR%\aide\stop.bat" (
    echo @echo off
    echo chcp 65001 ^>nul 2^>^&1
    echo taskkill /f /im python.exe /fi "WINDOWTITLE eq *uvicorn*" 2^>nul
    echo taskkill /f /fi "IMAGENAME eq python.exe" /fi "WINDOWTITLE eq *8900*" 2^>nul
    echo :: 更安全的方式：只杀监听8900端口的进程
    echo for /f "tokens=5" %%%%a in ^('netstat -aon ^| findstr :8900 ^| findstr LISTENING'^) do ^(
    echo     taskkill /f /pid %%%%a 2^>nul
    echo ^)
    echo echo [AIDE] 已停止
)

:: --- 桌面客户端启动 ---
if exist "%PKG_DIR%\aide\desktop\tray_icon.py" (
    > "%PKG_DIR%\aide\start_desktop.bat" (
        echo @echo off
        echo chcp 65001 ^>nul 2^>^&1
        echo set "ROOT=%%~dp0"
        echo set "ROOT=%%ROOT:~0,-1%%"
        echo cd /d "%%ROOT%%\desktop"
        echo if exist "%%ROOT%%\python\python.exe" ^(
        echo     "%%ROOT%%\python\python.exe" tray_icon.py
        echo ^) else ^(
        echo     python tray_icon.py
        echo ^)
        echo pause
    )
)

:: ===== [7/8] 生成Windows部署说明 =====
echo [7/8] 生成部署说明...

> "%PKG_DIR%\aide\WINDOWS部署说明.txt" (
    echo ========================================
    echo   AIDE 智能助手 v%VERSION% - Win10 部署指南
    echo ========================================
    echo.
    echo 【方式一：已有Python 3.8+】
    echo   1. 双击 install.bat
    echo   2. 双击 start.bat
    echo   3. 浏览器打开 http://127.0.0.1:8900
    echo.
    echo 【方式二：完全离线（无Python）】
    echo   1. 将嵌入式Python放入 python\ 目录
    echo      - 下载：https://www.python.org/ftp/python/3.8.10/python-3.8.10-embed-amd64.zip
    echo      - 解压到 python\python-3.8.10-embed-amd64\
    echo   2. 双击 install.bat
    echo   3. 双击 start.bat
    echo.
    echo 【方式三：U盘离线升级】
    echo   1. 将升级包(aide-update-vX.X.X.zip)复制到本项目根目录
    echo   2. 双击 upgrade_offline.bat 或在桌面客户端选择"U盘升级"
    echo.
    echo 【目录说明】
    echo   app\      - 程序代码（升级时覆盖）
    echo   config\   - 默认配置（升级时覆盖）
    echo   data\     - 你的数据（升级不碰！）
    echo   user\     - 你的配置和模板（升级不碰！）
    echo   output\   - 生成的文档（升级不碰）
    echo   logs\     - 运行日志
    echo   python\   - 嵌入式Python（可选）
    echo.
    echo 【修改配置】
    echo   编辑 user\user.env，优先级高于 config\default.env
    echo   升级时 user\user.env 不会被覆盖
    echo.
    echo 【使用手册】
    echo   docs\操作手册.md
    echo.
    echo 【联系支持】
    echo   数字化转型部
)

:: ===== [8/8] 打ZIP包 =====
echo [8/8] 打包ZIP...

:: 清理旧的包
del /q "%SCRIPT_DIR%\aide-offline-*-win10.zip" 2>nul

:: 使用PowerShell压缩
powershell -Command "Compress-Archive -Path '%PKG_DIR%\aide' -DestinationPath '%SCRIPT_DIR%\%PKG_NAME%.zip' -Force" 2>nul
if errorlevel 1 (
    :: 备选方案：使用7z
    if exist "C:\Program Files\7-Zip\7z.exe" (
        "C:\Program Files\7-Zip\7z.exe" a -tzip "%SCRIPT_DIR%\%PKG_NAME%.zip" "%PKG_DIR%\aide" >nul 2>&1
    ) else (
        echo [错误] 需要PowerShell 5+或7-Zip来创建ZIP
        echo [备选] 请手动将 aide\ 文件夹压缩为ZIP
        pause
        exit /b 1
    )
)

:: 显示文件大小
for %%f in ("%SCRIPT_DIR%\%PKG_NAME%.zip") do set "SIZE=%%~zf"
set /a "SIZE_MB=%SIZE% / 1048576"

:: 文件统计
set FILE_COUNT=0
for /f %%n in ('dir /s /b "%PKG_DIR%\aide" 2^>nul ^| find /c /v ""') do set "FILE_COUNT=%%n"

:: 清理临时目录
rmdir /s /q "%PKG_DIR%"

echo.
echo =========================================
echo   Win10 离线包制作完成！
echo =========================================
echo.
echo   文件: %PKG_NAME%.zip ^(%SIZE_MB% MB^)
echo   版本: v%VERSION%
echo   文件: %FILE_COUNT% 个
echo.
echo   部署步骤:
echo     1. 复制到目标Win10电脑
echo     2. 右键 → 解压
echo     3. 双击 install.bat
echo     4. 双击 start.bat
echo.
