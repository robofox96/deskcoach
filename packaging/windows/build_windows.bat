@echo off
setlocal enabledelayedexpansion

REM DeskCoach Windows build script (PyInstaller-based)
REM
REM This script builds an unsigned DeskCoach executable using
REM PyInstaller. It is intended for local development and QA,
REM not for code-signing or installer creation.
REM
REM Usage (from repo root, in CMD or PowerShell):
REM   packaging\windows\build_windows.bat

REM Resolve repository root (two levels up from this script).
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."
cd ..
set REPO_ROOT=%cd%

set APP_NAME=DeskCoach
set VENVDIR=venv

echo [build] Repository root: %REPO_ROOT%

REM Ensure virtualenv exists.
if not exist "%VENVDIR%\Scripts\python.exe" (
  echo [build] ERROR: %VENVDIR%\Scripts\python.exe not found. Create venv and install dependencies first:>&2
  echo         python -m venv venv>&2
  echo         venv\Scripts\activate>&2
  echo         pip install -r requirements.txt>&2
  exit /b 1
)

REM Activate virtualenv.
call "%VENVDIR%\Scripts\activate.bat"

REM Ensure dependencies are present. This is idempotent and safe to rerun.
echo [build] Ensuring Python dependencies are installed...
pip install --upgrade pip >nul
pip install -r requirements.txt >nul
pip install pyinstaller >nul

REM Clean previous build artifacts.
echo [build] Cleaning previous build artifacts...
if exist build rmdir /S /Q build
if exist dist rmdir /S /Q dist
if exist "%APP_NAME%.spec" del "%APP_NAME%.spec" 2>nul

echo [build] Running PyInstaller...
pyinstaller ^
  --clean --noconfirm ^
  --name "%APP_NAME%" ^
  --windowed ^
  --paths "%REPO_ROOT%" ^
  --collect-all streamlit ^
  --collect-submodules core ^
  --collect-submodules ui ^
  packaging\windows\entry_windows.py

if errorlevel 1 (
  echo [build] ERROR: PyInstaller failed.>&2
  exit /b 1
)

echo.
echo [build] Done.
echo.
echo Built app under:
echo   dist\%APP_NAME%\
echo.
echo To run DeskCoach on Windows:
echo   dist\%APP_NAME%\%APP_NAME%.exe

echo.
endlocal
