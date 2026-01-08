@echo off
setlocal enabledelayedexpansion

echo Clip Extractor Launcher
echo =====================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Check if PySide6 is installed
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo ERROR: PySide6 is not installed
    echo Installing PySide6...
    pip install PySide6
    if errorlevel 1 (
        echo ERROR: Failed to install PySide6
        pause
        exit /b 1
    )
)

REM Check for required ffmpeg binaries
set "missing_binaries="
if not exist "ffmpeg.exe" set "missing_binaries=!missing_binaries! ffmpeg.exe"
if not exist "ffprobe.exe" set "missing_binaries=!missing_binaries! ffprobe.exe"
if not exist "ffplay.exe" set "missing_binaries=!missing_binaries! ffplay.exe"

if not "!missing_binaries!"=="" (
    echo WARNING: Missing FFmpeg binaries:!missing_binaries!
    echo.
    echo Please download FFmpeg from https://ffmpeg.org/download.html
    echo Extract ffmpeg.exe, ffprobe.exe, and ffplay.exe to this folder.
    echo.
    echo The app will still launch but export functionality will not work.
    echo.
    pause
)

REM Launch the application
echo Starting Clip Extractor...
python main.py

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)

