@echo off
cd /d "%~dp0"
python server\daemon.py --host 0.0.0.0 --port 5050
pause
