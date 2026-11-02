# benchmarks/local_renderer.py
# Runs local FFmpeg rendering for baseline comparison.
# Results are used in the speedup calculation.

import subprocess
import time
import os
import shutil
from pathlib import Path
from typing import Optional
from shared.constants import ALLOWED_INPUT_EXTENSIONS


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def render_locally(
    input_path: str,
    output_path: str,
    resolution: str = "Original",
    bitrate: str = "4M",
    preset: str = "medium",
    output_format: str = "mp4",
) -> tuple[bool, float, str]:
    """
    Run local FFmpeg CPU render.
    Returns: (success, duration_seconds, error_message)
    """
    if not ffmpeg_available():
        return False, 0.0, "FFmpeg not found in PATH"

    args = ["ffmpeg", "-y", "-i", input_path, "-progress", "pipe:1", "-nostats"]

    if resolution != "Original":
        scale_map = {"1080p": "1920x1080", "720p": "1280x720", "480p": "854x480"}
        if resolution in scale_map:
            args += ["-vf", f"scale={scale_map[resolution]}"]

    args += ["-c:v", "libx264", "-preset", preset, "-b:v", bitrate]
    args += ["-c:a", "aac", "-b:a", "128k"]
    args.append(output_path)

    start = time.perf_counter()
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=3600
        )
        elapsed = time.perf_counter() - start
        if result.returncode == 0:
            return True, elapsed, ""
        return False, elapsed, f"FFmpeg error (code {result.returncode})"
    except subprocess.TimeoutExpired:
        return False, 0.0, "Local render timed out"
    except Exception as e:
        return False, 0.0, str(e)
