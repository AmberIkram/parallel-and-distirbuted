# server/engine/gpu_detector.py
# Detects actual GPU, CUDA, NVENC, and FFmpeg capabilities.
# Never pretends GPU is available when it is not.

import subprocess
import shutil
import re
from typing import Optional
from shared.models import GPUInfo
from server.utils.logger import get_logger

logger = get_logger("gpu_detector")


def _run(cmd: list[str], timeout: int = 10) -> Optional[str]:
    """Run a subprocess safely and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def detect_nvidia_gpu() -> tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Returns (gpu_name, vram_mb, driver_version) or (None, None, None).
    Uses nvidia-smi — the only reliable source of truth.
    """
    output = _run([
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits"
    ])
    if not output:
        return None, None, None

    parts = [p.strip() for p in output.split(",")]
    if len(parts) < 3:
        return None, None, None

    gpu_name = parts[0]
    try:
        vram_mb = int(parts[1])
    except ValueError:
        vram_mb = None
    driver_version = parts[2]
    return gpu_name, vram_mb, driver_version


def detect_cuda() -> bool:
    """Check CUDA via PyTorch if available."""
    try:
        import torch  # type: ignore
        return torch.cuda.is_available()
    except ImportError:
        return False


def detect_ffmpeg() -> tuple[bool, Optional[str]]:
    """Check if FFmpeg is installed and return its version."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False, None
    output = _run(["ffmpeg", "-version"])
    if output:
        match = re.search(r"ffmpeg version (\S+)", output)
        version = match.group(1) if match else "unknown"
        return True, version
    return False, None


def detect_nvenc(ffmpeg_available: bool) -> bool:
    """Check if NVENC encoder is available in this FFmpeg build."""
    if not ffmpeg_available:
        return False
    output = _run(["ffmpeg", "-encoders"])
    if output and "h264_nvenc" in output:
        # Also verify we can actually init an NVENC encode context
        test = _run([
            "ffmpeg", "-f", "lavfi", "-i", "color=black:s=128x128:d=1",
            "-c:v", "h264_nvenc", "-f", "null", "-"
        ], timeout=15)
        # None means it failed (no GPU), non-None means success
        # We check stderr too for actual failure detection
        try:
            result = subprocess.run(
                ["ffmpeg", "-f", "lavfi", "-i", "color=black:s=128x128:d=1",
                 "-c:v", "h264_nvenc", "-f", "null", "-"],
                capture_output=True, text=True, timeout=15
            )
            # nvenc fails with error if no GPU present
            if result.returncode == 0 or "frame=" in result.stderr:
                return True
        except Exception:
            pass
    return False


def detect_all() -> GPUInfo:
    """Run full hardware detection and return a GPUInfo object."""
    logger.info("Starting hardware detection...")

    gpu_name, vram_mb, driver_version = detect_nvidia_gpu()
    cuda_available = detect_cuda()
    ffmpeg_available, ffmpeg_version = detect_ffmpeg()
    nvenc_available = False

    if gpu_name:
        logger.info(f"NVIDIA GPU detected: {gpu_name} ({vram_mb} MB VRAM)")
        nvenc_available = detect_nvenc(ffmpeg_available)
    else:
        logger.info("No NVIDIA GPU detected — will use CPU rendering")

    if not ffmpeg_available:
        logger.warning("FFmpeg not found in PATH — rendering will not work")
    else:
        logger.info(f"FFmpeg version: {ffmpeg_version}")

    if nvenc_available:
        execution_mode = "NVENC"
    elif cuda_available:
        execution_mode = "CUDA"
    else:
        execution_mode = "CPU"

    logger.info(f"Execution mode: {execution_mode}")

    return GPUInfo(
        available=gpu_name is not None,
        gpu_name=gpu_name,
        vram_mb=vram_mb,
        cuda_available=cuda_available,
        nvenc_available=nvenc_available,
        driver_version=driver_version,
        ffmpeg_available=ffmpeg_available,
        ffmpeg_version=ffmpeg_version,
        execution_mode=execution_mode
    )


# Cached detection result — computed once at server startup
_cached_gpu_info: Optional[GPUInfo] = None


def get_gpu_info() -> GPUInfo:
    global _cached_gpu_info
    if _cached_gpu_info is None:
        _cached_gpu_info = detect_all()
    return _cached_gpu_info


def refresh_gpu_info() -> GPUInfo:
    global _cached_gpu_info
    _cached_gpu_info = detect_all()
    return _cached_gpu_info
