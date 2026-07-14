@echo off
setlocal

cd /d "%~dp0"

echo === MyOriShop installer ===

where uv >nul 2>nul
if errorlevel 1 (
  echo uv not found - installing via winget...
  winget install --id astral-sh.uv -e --source winget --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo winget install failed. Install uv manually: https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
  )
  echo uv installed. Re-run install.bat if "uv" is still not recognized ^(new terminal may be needed^).
)

echo Installing dependencies...
uv sync
if errorlevel 1 (
  echo uv sync failed.
  pause
  exit /b 1
)

echo Applying database migrations...
uv run alembic upgrade head
if errorlevel 1 (
  echo Migration failed.
  pause
  exit /b 1
)

echo Importing product dictionary and catalog prices...
uv run python scripts/import_master_pricelist.py
if errorlevel 1 (
  echo Dictionary import failed.
  pause
  exit /b 1
)

echo.
echo === Setup complete ===
echo Run the app with run.bat
pause
