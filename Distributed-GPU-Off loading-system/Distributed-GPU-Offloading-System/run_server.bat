@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  Distributed GPU Offloading System - SERVER
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Run setup.bat first.
    pause
    exit /b 1
)

:: Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] Virtual environment activated.
) else (
    echo [WARNING] No venv found. Running with system Python.
    echo Run setup.bat first for best results.
)

:: Check FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] FFmpeg not found - rendering will not work!
    echo Install FFmpeg and add it to PATH.
)

:: Create required directories
if not exist "uploads" mkdir uploads
if not exist "outputs" mkdir outputs
if not exist "logs" mkdir logs

echo.
echo Starting GPU Offloading Server...
echo Server config: config.json
echo Press Ctrl+C to stop the server.
echo.

python server/main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Server exited with an error.
    echo Check logs/ for details.
    pause
)
