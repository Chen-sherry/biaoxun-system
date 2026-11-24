@echo off
REM Windows 下启动后端（开发模式）
REM 需要先执行：python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt

cd /d %~dp0
if not exist .env (
    copy .env.example .env
    echo [INFO] 已生成默认 .env，请根据实际情况修改后再启动。
)

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
