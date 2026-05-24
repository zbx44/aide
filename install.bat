@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo =========================================
echo   AIDE 智能助手 v0.3 - Windows离线安装
echo   新版目录结构：app/config/data/user分离
echo =========================================
echo.

:: ===== 定位项目根目录 =====
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

:: ===== 步骤1: 配置Python =====
echo [1/5] 配置Python环境...

set "PYTHON_EXE="

:: 优先级1：内置嵌入版Python
if exist "%ROOT%\python\python.exe" (
    set "PYTHON_EXE=%ROOT%\python\python.exe"
    echo   [√] 找到内置Python: !PYTHON_EXE!
)

:: 优先级2：项目内venv
if not defined PYTHON_EXE if exist "%ROOT%\app\backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT%\app\backend\venv\Scripts\python.exe"
    echo   [√] 找到项目Python虚拟环境
)

:: 优先级3：旧版兼容 venv
if not defined PYTHON_EXE if exist "%ROOT%\backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT%\backend\venv\Scripts\python.exe"
    echo   [√] 找到旧版Python虚拟环境（兼容模式）
)

:: 优先级4：系统Python
if not defined PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%p in ('where python') do set "PYTHON_EXE=%%p"
        echo   [√] 找到系统Python: !PYTHON_EXE!
    )
)

if not defined PYTHON_EXE (
    echo.
    echo   [×] 未找到Python！
    echo.
    echo   解决方案（选择一种）：
    echo     方案A（推荐）：下载嵌入版Python放入 python\ 目录
    echo       1. 下载: https://www.python.org/ftp/python/3.8.10/python-3.8.10-embed-amd64.zip
    echo       2. 解压到: %ROOT%\python\python-3.8.10-embed-amd64\
    echo       3. 重新运行此脚本
    echo.
    echo     方案B：安装Python 3.8+
    echo       1. 下载: https://www.python.org/downloads/
    echo       2. 安装时勾选 "Add Python to PATH"
    echo       3. 重新运行此脚本
    echo.
    pause
    exit /b 1
)

echo.
echo   Python路径: !PYTHON_EXE!
"%PYTHON_EXE%" --version
echo.

:: ===== 解压嵌入式Python（如有） =====
if exist "%ROOT%\python\python-3.8.10-embed-*-amd64.zip" (
    echo   [信息] 检测到嵌入式Python压缩包，正在解压...
    for %%f in ("%ROOT%\python\python-3.8.10-embed-*-amd64.zip") do (
        set "ZIPNAME=%%~nf"
        mkdir "%ROOT%\python\!ZIPNAME!" 2>nul
        powershell -Command "Expand-Archive -Path '%%f' -DestinationPath '%ROOT%\python\!ZIPNAME!' -Force" 2>nul
        set "PYTHON_EXE=%ROOT%\python\!ZIPNAME!\python.exe"
    )
    echo   [√] 已解压到: !PYTHON_EXE!
    echo.
)

:: ===== 步骤2: 启用site-packages =====
echo [2/5] 启用site-packages支持...
for %%p in ("%ROOT%\python\*"."pth") do (
    if exist "%%p" (
        findstr /c:"import site" "%%p" >nul 2>&1
        if errorlevel 1 (
            echo import site>> "%%p"
            echo   [√] 已启用 %%~nxp 的site-packages
        )
    )
)

:: ===== 步骤3: 安装pip（嵌入版需要） =====
echo.
echo [3/5] 安装pip...
"%PYTHON_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
    :: 先尝试内置get-pip.py
    if exist "%ROOT%\python\get-pip.py" (
        echo   [信息] 使用内置get-pip.py安装...
        "%PYTHON_EXE%" "%ROOT%\python\get-pip.py" --no-wheel 2>nul
    )
    :: 如果还是失败，在线安装
    if errorlevel 1 (
        echo   [信息] 在线安装pip...
        "%PYTHON_EXE%" -m ensurepip 2>nul || (
            curl -sSL https://bootstrap.pypa.io/get-pip.py -o "%TEMP%\get-pip.py" 2>nul
            "%PYTHON_EXE%" "%TEMP%\get-pip.py" 2>nul
        )
    )
)

"%PYTHON_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo   [×] pip安装失败，请检查网络连接
    pause
    exit /b 1
)
echo   [√] pip已就绪

:: ===== 步骤4: 安装依赖 =====
echo.
echo [4/5] 安装应用依赖...

:: 确定后端目录
set "BACKEND_DIR="
if exist "%ROOT%\app\backend\requirements.txt" (
    set "BACKEND_DIR=%ROOT%\app\backend"
) else if exist "%ROOT%\backend\requirements.txt" (
    set "BACKEND_DIR=%ROOT%\backend"
)

if defined BACKEND_DIR (
    echo   [信息] 安装后端依赖...
    
    :: 优先从本地pip_cache离线安装
    if exist "%ROOT%\pip_cache_win10" (
        echo   [信息] 从离线包安装...
        "%PYTHON_EXE%" -m pip install --no-index --find-links="%ROOT%\pip_cache_win10" -r "%BACKEND_DIR%\requirements.txt" 2>nul
        if errorlevel 1 (
            echo   [警告] 部分包离线安装失败，尝试在线补充...
            "%PYTHON_EXE%" -m pip install -r "%BACKEND_DIR%\requirements.txt" -q
        )
    ) else if exist "%ROOT%\pip_cache" (
        echo   [信息] 从离线包安装（兼容目录）...
        "%PYTHON_EXE%" -m pip install --no-index --find-links="%ROOT%\pip_cache" -r "%BACKEND_DIR%\requirements.txt" 2>nul
        if errorlevel 1 (
            echo   [警告] 部分包离线安装失败，尝试在线补充...
            "%PYTHON_EXE%" -m pip install -r "%BACKEND_DIR%\requirements.txt" -q
        )
    ) else (
        echo   [信息] 在线安装依赖...
        "%PYTHON_EXE%" -m pip install -r "%BACKEND_DIR%\requirements.txt" -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    )
    
    :: 显示安装结果
    echo.
    echo   [√] 依赖安装完成
) else (
    echo   [×] 未找到requirements.txt
)

:: 桌面客户端依赖（可选）
if exist "%ROOT%\desktop\requirements.txt" (
    echo.
    echo   [信息] 桌面客户端依赖（可选）...
    if exist "%ROOT%\pip_cache_desktop" (
        "%PYTHON_EXE%" -m pip install --no-index --find-links="%ROOT%\pip_cache_desktop" -r "%ROOT%\desktop\requirements.txt" 2>nul
    ) else (
        "%PYTHON_EXE%" -m pip install -r "%ROOT%\desktop\requirements.txt" -q 2>nul
    )
    if errorlevel 1 (
        echo   [提示] 桌面客户端依赖安装失败（可选功能，不影响使用）
    ) else (
        echo   [√] 桌面客户端依赖安装完成
    )
)

:: ===== 步骤5: 初始化用户目录 =====
echo.
echo [5/5] 初始化用户数据目录...

cd /d "%ROOT%"

:: 创建用户数据目录（不碰已有数据）
if not exist "data" mkdir "data"
if not exist "user" mkdir "user"
if not exist "user\tasks" mkdir "user\tasks"
if not exist "user\templates" mkdir "user\templates"
if not exist "output" mkdir "output"
if not exist "logs" mkdir "logs"

:: 用户配置（只创建不覆盖）
if not exist "user\user.env" (
    > "user\user.env" (
        echo # AIDE 用户自定义配置
        echo # 此文件优先级高于 config\default.env
        echo # 升级时不会被覆盖，请放心修改
        echo.
        echo # 示例：修改默认端口
        echo # SERVER_PORT=8900
    )
    echo   [√] 已创建 user\user.env
) else (
    echo   [√] user\user.env 已存在（保留您的配置）
)

:: 运行数据迁移（如果有）
if exist "%ROOT%\migrate.py" (
    echo.
    echo   [信息] 运行数据迁移...
    "%PYTHON_EXE%" "%ROOT%\migrate.py" 2>nul
)

:: ===== 生成启动脚本 =====
echo.
echo [信息] 生成启动脚本...

:: --- 核心：start.bat（自动检测Python） ---
> "%ROOT%\start.bat" (
    echo @echo off
    echo chcp 65001 ^>nul 2^>^&1
    echo setlocal enabledelayedexpansion
    echo.
    echo :: 定位项目根目录
    echo set "ROOT=%%~dp0"
    echo set "ROOT=%%ROOT:~0,-1%%"
    echo set AIDE_ROOT=%%ROOT%%
    echo.
    echo :: 检测Python
    echo set "PYTHON_EXE="
    echo if exist "%%ROOT%%\python\python.exe" set "PYTHON_EXE=%%ROOT%%\python\python.exe"
    echo if not defined PYTHON_EXE if exist "%%ROOT%%\app\backend\venv\Scripts\python.exe" set "PYTHON_EXE=%%ROOT%%\app\backend\venv\Scripts\python.exe"
    echo if not defined PYTHON_EXE if exist "%%ROOT%%\backend\venv\Scripts\python.exe" set "PYTHON_EXE=%%ROOT%%\backend\venv\Scripts\python.exe"
    echo if not defined PYTHON_EXE ^(
    echo     where python ^>nul 2^>^&1
    echo     if not errorlevel 1 for /f "delims=" %%%%p in ^('where python'^) do set "PYTHON_EXE=%%%%p"
    echo ^)
    echo if not defined PYTHON_EXE ^(
    echo     echo [错误] 未找到Python，请先运行 install.bat
    echo     pause
    echo     exit /b 1
    echo ^)
    echo.
    echo :: 创建数据目录
    echo if not exist "%%ROOT%%\data" mkdir "%%ROOT%%\data"
    echo if not exist "%%ROOT%%\user" mkdir "%%ROOT%%\user"
    echo if not exist "%%ROOT%%\output" mkdir "%%ROOT%%\output"
    echo if not exist "%%ROOT%%\logs" mkdir "%%ROOT%%\logs"
    echo.
    echo :: 启动后端
    echo if exist "%%ROOT%%\app\backend" ^(
    echo     cd /d "%%ROOT%%\app\backend"
    echo ^) else if exist "%%ROOT%%\backend" ^(
    echo     cd /d "%%ROOT%%\backend"
    echo ^)
    echo.
    echo echo.
    echo echo =========================================
    echo echo   AIDE 智能助手 v0.3
    echo echo =========================================
    echo echo.
    echo echo   浏览器访问 http://127.0.0.1:8900
    echo echo   按 Ctrl+C 停止服务
    echo echo.
    echo.
    echo "%%PYTHON_EXE%%" -m uvicorn main:app --host 127.0.0.1 --port 8900
    echo.
    echo pause
)

:: --- stop.bat ---
> "%ROOT%\stop.bat" (
    echo @echo off
    echo chcp 65001 ^>nul 2^>^&1
    echo echo [AIDE] 正在停止...
    echo for /f "tokens=5" %%%%a in ^('netstat -aon ^| findstr :8900 ^| findstr LISTENING'^) do taskkill /f /pid %%%%a 2^>nul
    echo echo [AIDE] 已停止
    echo timeout /t 2 ^>nul
)

:: --- 桌面客户端启动 ---
if exist "%ROOT%\desktop\tray_icon.py" (
    > "%ROOT%\start_desktop.bat" (
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

:: --- U盘离线升级 ---
> "%ROOT%\upgrade_offline.bat" (
    echo @echo off
    echo chcp 65001 ^>nul 2^>^&1
    echo setlocal enabledelayedexpansion
    echo set "ROOT=%%~dp0"
    echo set "ROOT=%%ROOT:~0,-1%%"
    echo.
    echo echo =========================================
    echo echo   AIDE 离线升级
    echo echo =========================================
    echo echo.
    echo.
    echo :: 查找升级包
    echo set "UPDATE_ZIP="
    echo for %%%%f in ^("%%ROOT%%\aide-update-v*.zip"^) do set "UPDATE_ZIP=%%%%f"
    echo.
    echo if not defined UPDATE_ZIP ^(
    echo     echo [错误] 未找到升级包！
    echo     echo.
    echo     echo 请将升级包 ^(aide-update-vX.X.X.zip^) 复制到：
    echo     echo   %%ROOT%%\
    echo     echo.
    echo     pause
    echo     exit /b 1
    echo ^)
    echo.
    echo echo [信息] 找到升级包: %%UPDATE_ZIP%%
    echo set /p CONFIRM="确认升级？^(Y/N^): "
    echo if /i not "%%CONFIRM%%"=="Y" ^(
    echo     echo 已取消
    echo     pause
    echo     exit /b 0
    echo ^)
    echo.
    echo :: 停止服务
    echo call "%%ROOT%%\stop.bat" 2^>nul
    echo timeout /t 3 ^>nul
    echo.
    echo :: 备份
    echo set "BACKUP_DIR=%%ROOT%%\backup\%%date:~0,4%%%%date:~5,2%%%%date:~8,2%%_%%time:~0,2%%%%time:~3,2%%"
    echo set "BACKUP_DIR=%%BACKUP_DIR: =0%%"
    echo mkdir "%%BACKUP_DIR%%" 2^>nul
    echo xcopy "%%ROOT%%\app" "%%BACKUP_DIR%%\app\" /e /i /q ^>nul 2^>^&1
    echo xcopy "%%ROOT%%\config" "%%BACKUP_DIR%%\config\" /e /i /q ^>nul 2^>^&1
    echo echo [√] 已备份到 %%BACKUP_DIR%%
    echo.
    echo :: 解压升级包
    echo powershell -Command "Expand-Archive -Path '%%UPDATE_ZIP%%' -DestinationPath '%%ROOT%%\aide-update-temp' -Force" 2^>nul
    echo.
    echo :: 覆盖app和config（不动data/user/output）
    echo if exist "%%ROOT%%\aide-update-temp\app" ^(
    echo     rmdir /s /q "%%ROOT%%\app" 2^>nul
    echo     xcopy "%%ROOT%%\aide-update-temp\app" "%%ROOT%%\app\" /e /i /q ^>nul 2^>^&1
    echo ^)
    echo if exist "%%ROOT%%\aide-update-temp\config" ^(
    echo     xcopy "%%ROOT%%\aide-update-temp\config" "%%ROOT%%\config\" /e /i /q /d ^>nul 2^>^&1
    echo ^)
    echo.
    echo :: 清理
    echo rmdir /s /q "%%ROOT%%\aide-update-temp" 2^>nul
    echo.
    echo echo.
    echo echo =========================================
    echo echo   升级完成！双击 start.bat 启动
    echo echo =========================================
    echo echo.
    echo pause
)

:: ===== 创建桌面快捷方式 =====
echo.
echo [信息] 创建桌面快捷方式...

set "SHORTCUT_NAME=AIDE 智能助手"
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\%SHORTCUT_NAME%.lnk"
set "ICON_PATH=%ROOT%\app\backend\static\favicon.ico"

if not exist "%ICON_PATH%" set "ICON_PATH=%ROOT%\backend\static\favicon.ico"

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%ROOT%\start.bat'; $s.WorkingDirectory = '%ROOT%'; if (Test-Path '%ICON_PATH%') { $s.IconLocation = '%ICON_PATH%,0' }; $s.Save()" 2>nul

:: ===== 完成 =====
echo.
echo =========================================
echo   安装完成！
echo =========================================
echo.
echo 🚀 启动方式:
echo   双击桌面快捷方式 "%SHORTCUT_NAME%"
echo   或双击 start.bat
echo.
echo 🛑 停止: 双击 stop.bat
echo.
echo 🌐 浏览器访问: http://127.0.0.1:8900
echo.
echo 📂 目录说明：
echo   app\     - 程序代码（升级时覆盖）
echo   config\  - 默认配置（升级时覆盖）
echo   data\    - 你的数据（升级不碰！）
echo   user\    - 你的配置和模板（升级不碰！）
echo   output\  - 生成的文档（升级不碰）
echo   logs\    - 运行日志
echo.
echo 💡 如需修改配置，编辑 user\user.env 即可
echo 📖 使用手册：docs\操作手册.md
echo.
echo ⬆️ 离线升级：将升级包放在根目录，双击 upgrade_offline.bat
echo.
pause
