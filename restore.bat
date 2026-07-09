@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: restore.bat backups\myorishop-YYYYMMDD-HHMMSS.db
  dir /b backups
  pause
  exit /b 1
)
rem The app MUST be stopped before restoring - close the server window first.
copy /y "%~1" data\myorishop.db
rem Delete stale WAL sidecars: SQLite would replay the OLD wal into the
rem restored file and corrupt it (sqlite.org/howtocorrupt.html 1.4).
del /q data\myorishop.db-wal 2>nul
del /q data\myorishop.db-shm 2>nul
echo Restore complete. Start the app with run.bat.
pause
