@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ===== AIDE 智能助手 - 启动脚本 =====
REM 自动检测目录结构，支持新旧两种布局

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

REM 检测目录结构
if exist "%ROOT%\app\backend\main.py" (
    set "BACKEND=%ROOT%\app\backend"
    echo [AIDE] 使用新版目录结构
) else (
    set "BACKEND=%ROOT%\backend"
    echo [AIDE] 使用旧版目录结构（兼容模式）
)

REM 设置根目录环境变量
set AIDE_ROOT=%ROOT%

REM 创建必要目录
if not exist "%ROOT%\data" mkdir "%ROOT%\data"
if not exist "%ROOT%\user" mkdir "%ROOT%\user"
if not exist "%ROOT%\output" mkdir "%ROOT%\output"
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"

REM 查找Python
set "PYTHON_EXE="
if exist "%ROOT%\python\python.exe" (
    set "PYTHON_EXE=%ROOT%\python\python.exe"
) else if exist "%BACKEND%\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%BACKEND%\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [AIDE] Python: %PYTHON_EXE%
echo [AIDE] 根目录: %ROOT%
echo [AIDE] 数据目录: %ROOT%\data
echo.
echo [AIDE] 启动中...
echo [AIDE] 浏览器访问: http://127.0.0.1:8900
echo.

cd /d "%BACKEND%"
"%PYTHON_EXE%" -m uvicorn main:app --host 127.0.0.1 --port 8900
pause
