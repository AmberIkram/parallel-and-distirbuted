@echo off
python --version
where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo FFmpeg was not found on PATH. Install FFmpeg and add its bin folder to PATH.
  pause
  exit /b 1
)
echo Environment check completed.
pause
