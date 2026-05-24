@echo off
:: 启动桌面客户端
cd /d "%~dp0desktop"
call ..\backend\venv\Scripts\activate.bat
python main.py
