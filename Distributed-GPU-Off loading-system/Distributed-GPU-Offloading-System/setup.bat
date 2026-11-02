@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  Distributed GPU Offloading System - Setup
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found:
python --version

:: Check pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip is not available.
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist "venv" (
    echo.
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

:: Activate and install dependencies
echo.
echo Installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.

:: Create required directories
echo.
echo Creating required directories...
if not exist "uploads" mkdir uploads
if not exist "outputs" mkdir outputs
if not exist "logs" mkdir logs
if not exist "benchmarks\results" mkdir benchmarks\results
echo [OK] Directories ready.

:: Check FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARNING] FFmpeg not found in PATH.
    echo Please install FFmpeg from https://ffmpeg.org/download.html
    echo Add FFmpeg to your system PATH for rendering to work.
) else (
    echo [OK] FFmpeg found.
)

echo.
echo ============================================================
echo  Setup complete!
echo  - To start the SERVER: run_server.bat
echo  - To start the CLIENT: run_client.bat
echo ============================================================
pause
