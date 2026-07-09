@echo off
cd /d "%~dp0"
uv run python scripts\reset_demo_data.py
pause
