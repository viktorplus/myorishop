@echo off
cd /d "%~dp0"
uv run alembic upgrade head
if errorlevel 1 (
  echo Migration failed - server not started.
  pause
  exit /b 1
)
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000"
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
