@echo off
cd /d "%~dp0"
uv run python scripts\import_master_pricelist.py %*
pause
