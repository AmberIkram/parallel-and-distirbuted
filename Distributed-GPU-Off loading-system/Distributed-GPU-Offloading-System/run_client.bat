@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  Distributed GPU Offloading System - CLIENT
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
)

:: Create required directories
if not exist "outputs" mkdir outputs
if not exist "logs" mkdir logs

echo.
echo Launching GPU Offloading Dashboard...
echo.

python client/main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Client exited with an error.
    echo Check logs/ for details.
    pause
)
