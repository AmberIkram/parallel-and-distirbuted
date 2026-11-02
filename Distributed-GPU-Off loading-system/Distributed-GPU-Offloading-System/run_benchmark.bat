@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  Distributed GPU Offloading System - BENCHMARK
echo ============================================================
echo.

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

if "%~1"=="" (
    echo Usage: run_benchmark.bat [video_file] [server_ip]
    echo.
    echo Examples:
    echo   run_benchmark.bat assets\demo\sample.mp4
    echo   run_benchmark.bat assets\demo\sample.mp4 192.168.1.1
    echo   run_benchmark.bat assets\demo\sample.mp4 192.168.1.1 --local-only
    echo.
    pause
    exit /b 0
)

set VIDEO=%~1
set SERVER_IP=%~2

if "%SERVER_IP%"=="" (
    python benchmarks/benchmark.py --input "%VIDEO%" --local-only
) else (
    python benchmarks/benchmark.py --input "%VIDEO%" --server-ip "%SERVER_IP%" %~3
)

echo.
echo Benchmark results saved to benchmarks/results/
pause
