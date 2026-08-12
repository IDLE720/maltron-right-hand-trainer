@echo off
setlocal
cd /d "%~dp0"

rem Prefer the installed Python launcher and preserve this script's full path.
where pyw.exe >nul 2>nul
if not errorlevel 1 (
  start "Right Hand Quest Overlay" pyw.exe -3 "%~dp0key-overlay.py"
  exit /b
)

where pythonw.exe >nul 2>nul
if not errorlevel 1 (
  start "Right Hand Quest Overlay" pythonw.exe "%~dp0key-overlay.py"
  exit /b
)

msg * "Python 3 was not found. Install Python 3 or run key-overlay.py with Python."
