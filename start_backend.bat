@echo off
:: 启动后端服务
cd /d "%~dp0backend"
call venv\Scripts\activate.bat
python -m uvicorn main:app --host 127.0.0.1 --port 8900 --reload
