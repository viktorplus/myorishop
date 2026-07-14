@echo off
cd /d "%~dp0"

rem Kill any stale server left listening on 127.0.0.1:8000 from a previous
rem run.bat launch, so a leftover process on old code can't keep answering
rem requests after a git pull / new commits.
for /f "tokens=5" %%P in ('netstat -ano ^| findstr "127.0.0.1:8000" ^| findstr "LISTENING"') do (
  echo Stopping stale server on port 8000, PID %%P ...
  taskkill /F /PID %%P >nul 2>&1
)

uv run alembic upgrade head
if errorlevel 1 (
  echo Migration failed - server not started.
  pause
  exit /b 1
)
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000"
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
