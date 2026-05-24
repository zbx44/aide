@echo off
chcp 65001 >nul 2>&1
REM AIDE 智能助手 - 停止脚本
taskkill /f /im uvicorn.exe 2>nul
if errorlevel 1 (
    echo [AIDE] 未找到运行中的服务
) else (
    echo [AIDE] 已停止
)
