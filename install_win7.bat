@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo =========================================
echo   AIDE v0.3 - Windows 7 离线安装
echo   Python 3.8.10 嵌入版（完全不联网）
echo =========================================
echo.

:: ===== 定位根目录 =====
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "AIDE_ROOT=%ROOT%\aide"
set "PYTHON_DIR=%ROOT%\python\python-3.8.10-embed-amd64"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "SITE=%PYTHON_DIR%\Lib\site-packages"
set "PKG=%ROOT%\packages"

:: ===== Step 1: 解压Python =====
echo [1/5] 配置Python 3.8.10...

if not exist "%PYTHON_EXE%" (
    if not exist "%ROOT%\python\python-3.8.10-embed-amd64.zip" (
        echo   [X] 未找到 python\python-3.8.10-embed-amd64.zip
        pause
        exit /b 1
    )
    echo   正在解压Python...
    if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"
    :: 用VBScript解压，兼容Win7且不依赖PowerShell
    echo Set objShell = CreateObject("Shell.Application") > "%TEMP%\_aide_unzip.vbs"
    echo Set objSource = objShell.NameSpace("%ROOT%\python\python-3.8.10-embed-amd64.zip") >> "%TEMP%\_aide_unzip.vbs"
    echo Set objDest = objShell.NameSpace("%PYTHON_DIR%") >> "%TEMP%\_aide_unzip.vbs"
    echo objDest.CopyHere objSource.Items, 16+256+1024 >> "%TEMP%\_aide_unzip.vbs"
    cscript //nologo "%TEMP%\_aide_unzip.vbs"
    del "%TEMP%\_aide_unzip.vbs" 2>nul
)

echo   [OK] %PYTHON_EXE%
"%PYTHON_EXE%" --version

:: ===== Step 2: 配置 _pth =====
echo.
echo [2/5] 配置Python路径...

(
    echo python38.zip
    echo .
    echo Lib
    echo Lib\site-packages
    echo Scripts
    echo import site
) > "%PYTHON_DIR%\python38._pth"

if not exist "%PYTHON_DIR%\Lib" mkdir "%PYTHON_DIR%\Lib"
if not exist "%SITE%" mkdir "%SITE%"
if not exist "%PYTHON_DIR%\Scripts" mkdir "%PYTHON_DIR%\Scripts"

echo   [OK]

:: ===== Step 3: 用Python zipfile解压所有whl =====
echo.
echo [3/5] 安装依赖（Python zipfile解压，兼容Win7）...
echo   共59个包，请耐心等待约1-2分钟...

:: 写一个Python脚本一次性解压所有whl，比逐个调用快得多
set "EXTRACT_SCRIPT=%TEMP%\_aide_extract.py"
(
    echo import zipfile
    echo import os
    echo import sys
    echo pkg_dir = r'%PKG%'
    echo site_dir = r'%SITE%'
    echo files = sorted([f for f in os.listdir(pkg_dir) if f.endswith('.whl')])
    echo total = len(files)
    echo for i, fname in enumerate(files, 1):
    echo     fpath = os.path.join(pkg_dir, fname)
    echo     sys.stdout.write(f'  [{i}/{total}] {fname} ... ')
    echo     sys.stdout.flush()
    echo     try:
    echo         with zipfile.ZipFile(fpath, 'r') as zf:
    echo             zf.extractall(site_dir)
    echo         print('[OK]')
    echo     except Exception as e:
    echo         print(f'[FAIL] {e}')
) > "%EXTRACT_SCRIPT%"

"%PYTHON_EXE%" "%EXTRACT_SCRIPT%"
del "%EXTRACT_SCRIPT%" 2>nul

:: 写入 .dist-info 的 INSTALLER 文件（让uvicorn -m 能找到）
echo pip > "%SITE%\uvicorn-0.33.0.dist-info\INSTALLER" 2>nul

:: ===== Step 4: 验证 =====
echo.
echo [4/5] 验证核心模块...

echo import fastapi, uvicorn, pydantic > "%TEMP%\_aide_chk.py"
echo import yaml, jinja2, openai, httpx >> "%TEMP%\_aide_chk.py"
echo import docx, openpyxl, pptx >> "%TEMP%\_aide_chk.py"
echo print("ALL_OK") >> "%TEMP%\_aide_chk.py"

"%PYTHON_EXE%" "%TEMP%\_aide_chk.py"
if errorlevel 1 (
    echo   [X] 验证失败 - 依赖安装不完整
    echo   请检查上方是否有[FAIL]项
) else (
    echo   [OK] 核心模块全部正常
)
del "%TEMP%\_aide_chk.py" 2>nul

:: ===== Step 5: 初始化 + 生成启动脚本 =====
echo.
echo [5/5] 初始化...

cd /d "%AIDE_ROOT%"

if not exist "data" mkdir "data"
if not exist "user" mkdir "user"
if not exist "user\tasks" mkdir "user\tasks"
if not exist "user\templates" mkdir "user\templates"
if not exist "output" mkdir "output"
if not exist "logs" mkdir "logs"
if not exist "backup" mkdir "backup"

if not exist "user\user.env" (
    echo # AIDE 用户自定义配置 > "user\user.env"
    echo # 优先级高于 config\default.env >> "user\user.env"
    echo # 升级时不会覆盖 >> "user\user.env"
)

:: --- start.bat ---
> "%AIDE_ROOT%\start.bat" (
    echo @echo off
    echo chcp 65001 ^>nul
    echo set "ROOT=%%~dp0"
    echo if "%%ROOT:~-1%%"=="\" set "ROOT=%%ROOT:~0,-1%%"
    echo set AIDE_ROOT=%%ROOT%%
    echo if not exist "%%ROOT%%\data" mkdir "%%ROOT%%\data"
    echo if not exist "%%ROOT%%\user" mkdir "%%ROOT%%\user"
    echo if not exist "%%ROOT%%\output" mkdir "%%ROOT%%\output"
    echo if not exist "%%ROOT%%\logs" mkdir "%%ROOT%%\logs"
    echo if exist "%%ROOT%%\app\backend" cd /d "%%ROOT%%\app\backend"
    echo echo.
    echo echo =========================================
    echo echo   AIDE 智能助手 v0.3 ^| Win7
    echo echo =========================================
    echo echo.
    echo echo   浏览器访问 http://127.0.0.1:8900
    echo echo   按 Ctrl+C 停止
    echo echo.
    echo "%PYTHON_EXE%" -m uvicorn main:app --host 127.0.0.1 --port 8900
    echo pause
)

:: --- stop.bat ---
> "%AIDE_ROOT%\stop.bat" (
    echo @echo off
    echo chcp 65001 ^>nul
    echo for /f "tokens=5" %%%%a in ^('netstat -aon ^| findstr :8900 ^| findstr LISTENING'^) do taskkill /f /pid %%%%a 2^>nul
    echo echo [AIDE] 已停止
    echo timeout /t 2 ^>nul
)

echo   [OK]

echo.
echo =========================================
echo   安装完成！
echo =========================================
echo.
echo   启动: 双击 aide\start.bat
echo   停止: 双击 aide\stop.bat
echo   访问: http://127.0.0.1:8900
echo.
pause
