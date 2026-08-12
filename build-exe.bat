@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%LocalAppData%\Programs\Python\Python313\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo Installing PyInstaller...
  "%PYTHON%" -m pip install pyinstaller
  if errorlevel 1 goto :failed
)

echo Building RightHandQuestOverlay.exe...
"%PYTHON%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name RightHandQuestOverlay ^
  key-overlay.py
if errorlevel 1 goto :failed

echo.
echo Build complete:
echo %~dp0dist\RightHandQuestOverlay.exe
exit /b 0

:failed
echo.
echo Build failed.
pause
exit /b 1
