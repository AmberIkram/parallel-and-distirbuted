# server/engine/ffmpeg_engine.py
# Handles actual FFmpeg video transcoding with real progress parsing.
# Never uses shell=True. All arguments are passed as lists.

import subprocess
import asyncio
import re
import time
from pathlib import Path
from typing import Callable, Optional, AsyncGenerator
from shared.models import RenderConfig, GPUInfo
from server.utils.logger import get_logger

logger = get_logger("ffmpeg_engine")

# Resolution map
RESOLUTION_MAP = {
    "1080p": "1920x1080",
    "720p":  "1280x720",
    "480p":  "854x480",
}


def _get_video_duration(input_path: str, ffprobe: str = "ffprobe") -> Optional[float]:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", input_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _build_ffmpeg_args(
    input_path: str,
    output_path: str,
    config: RenderConfig,
    gpu_info: GPUInfo,
    ffmpeg_bin: str = "ffmpeg"
) -> tuple[list[str], str]:
    """
    Build safe FFmpeg argument list.
    Returns (args_list, execution_device_label).
    Never passes user input directly to shell.
    """
    args = [ffmpeg_bin, "-y"]

    # Input
    args += ["-i", input_path]

    # Progress reporting to stdout
    args += ["-progress", "pipe:1", "-nostats"]

    # Determine encoder
    use_nvenc = (
        gpu_info.nvenc_available and
        config.execution_mode in ("auto", "gpu")
    )

    if use_nvenc:
        encoder = "h264_nvenc"
        execution_device = "NVENC"
        # NVENC preset mapping
        nvenc_preset = {"fast": "p1", "medium": "p4", "slow": "p7"}.get(
            config.preset, "p4"
        )
        args += ["-c:v", encoder, "-preset", nvenc_preset]
    else:
        encoder = "libx264"
        execution_device = "CPU"
        # libx264 preset
        preset = config.preset if config.preset in ("fast", "medium", "slow") else "medium"
        args += ["-c:v", encoder, "-preset", preset]

    # Bitrate
    bitrate = config.custom_bitrate if config.bitrate == "custom" and config.custom_bitrate else config.bitrate
    if bitrate and bitrate != "0":
        args += ["-b:v", bitrate]

    # Resolution
    if config.resolution != "Original" and config.resolution in RESOLUTION_MAP:
        scale = RESOLUTION_MAP[config.resolution]
        args += ["-vf", f"scale={scale}"]

    # Audio: copy by default
    args += ["-c:a", "aac", "-b:a", "128k"]

    # Output
    args.append(output_path)

    return args, execution_device


async def render_video(
    input_path: str,
    output_path: str,
    config: RenderConfig,
    gpu_info: GPUInfo,
    progress_callback: Callable[[float, str], None],
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> tuple[bool, str, float]:
    """
    Render a video asynchronously using FFmpeg.

    Args:
        input_path: absolute path to input file
        output_path: absolute path to output file
        config: rendering configuration
        gpu_info: detected GPU capabilities
        progress_callback: async-compatible callback(progress_pct, message)
        ffmpeg_bin: path to ffmpeg executable
        ffprobe_bin: path to ffprobe executable

    Returns:
        (success, execution_device, duration_seconds)
    """
    duration = _get_video_duration(input_path, ffprobe_bin)
    args, execution_device = _build_ffmpeg_args(
        input_path, output_path, config, gpu_info, ffmpeg_bin
    )

    logger.info(f"FFmpeg command: {' '.join(args)}")
    logger.info(f"Execution device: {execution_device}")
    logger.info(f"Input duration: {duration}s")

    start_time = time.time()

    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        current_time_us = 0.0

        async def read_progress():
            nonlocal current_time_us
            if process.stdout is None:
                return
            async for line in process.stdout:
                text = line.decode("utf-8", errors="replace").strip()
                # FFmpeg -progress pipe:1 outputs key=value pairs
                if text.startswith("out_time_us="):
                    try:
                        current_time_us = float(text.split("=")[1])
                        if duration and duration > 0:
                            pct = min(99.0, (current_time_us / 1_000_000) / duration * 100)
                            elapsed = time.time() - start_time
                            eta = None
                            if pct > 0:
                                eta = (elapsed / pct) * (100 - pct)
                            msg = f"Rendering at {pct:.1f}% | Device: {execution_device}"
                            progress_callback(pct, msg)
                    except (ValueError, ZeroDivisionError):
                        pass
                elif text.startswith("progress=end"):
                    progress_callback(99.9, f"Finalizing... | Device: {execution_device}")

        async def drain_stderr():
            if process.stderr is None:
                return
            async for _ in process.stderr:
                pass  # drain stderr to prevent pipe blocking

        await asyncio.gather(read_progress(), drain_stderr())
        await process.wait()

        elapsed = time.time() - start_time

        if process.returncode == 0:
            progress_callback(100.0, f"Rendering complete | Device: {execution_device}")
            logger.info(f"Rendering completed in {elapsed:.2f}s using {execution_device}")
            return True, execution_device, elapsed
        else:
            # Collect stderr for error message
            err_msg = f"FFmpeg exited with code {process.returncode}"
            logger.error(err_msg)
            return False, execution_device, elapsed

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"FFmpeg rendering exception: {e}")
        return False, execution_device, elapsed
