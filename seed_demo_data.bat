@echo off
cd /d "%~dp0"
uv run python scripts\seed_demo_data.py %*
pause
