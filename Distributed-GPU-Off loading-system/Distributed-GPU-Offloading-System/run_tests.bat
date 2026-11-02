@echo off
echo ============================================================
echo  Distributed GPU Offloading System - TESTS
echo ============================================================
echo.

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo Running unit tests (no server required)...
python -m pytest tests/test_checksum.py tests/test_task_manager.py tests/test_api.py -v

echo.
echo To run integration tests with a live server:
echo   python -m pytest tests/ -v --integration --server-url http://SERVER_IP:8000
echo.
pause
