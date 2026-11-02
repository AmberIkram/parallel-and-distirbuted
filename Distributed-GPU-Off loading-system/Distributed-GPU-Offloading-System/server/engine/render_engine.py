# server/engine/render_engine.py
# Orchestrates the rendering pipeline for a single job.

import asyncio
from pathlib import Path
from typing import Callable
from shared.models import RenderConfig, JobStatus
from shared.constants import STATUS_PROCESSING, STATUS_COMPLETED, STATUS_FAILED
from server.engine.ffmpeg_engine import render_video
from server.engine.gpu_detector import get_gpu_info
from server.utils.config import CONFIG
from server.utils.logger import get_logger

logger = get_logger("render_engine")


async def execute_render_job(
    job: JobStatus,
    progress_callback: Callable[[float, str, str], None],
) -> JobStatus:
    """
    Execute a rendering job end-to-end.

    Args:
        job: the JobStatus object (must have status=processing)
        progress_callback: called with (progress_pct, message, execution_device)

    Returns:
        Updated JobStatus
    """
    gpu_info = get_gpu_info()
    upload_dir = Path(CONFIG.get("upload_dir", "uploads"))
    output_dir = Path(CONFIG.get("output_dir", "outputs"))
    output_dir.mkdir(parents=True, exist_ok=True)

    input_path = upload_dir / job.input_filename
    output_ext = job.render_config.output_format.lstrip(".")
    output_filename = f"{job.job_id}_output.{output_ext}"
    output_path = output_dir / output_filename

    if not input_path.exists():
        job.status = STATUS_FAILED
        job.error_message = f"Input file not found: {job.input_filename}"
        logger.error(job.error_message)
        return job

    def sync_callback(pct: float, msg: str):
        device = "CPU"
        if gpu_info.nvenc_available and job.render_config.execution_mode in ("auto", "gpu"):
            device = "NVENC"
        elif gpu_info.cuda_available:
            device = "CUDA"
        progress_callback(pct, msg, device)

    success, execution_device, duration = await render_video(
        input_path=str(input_path),
        output_path=str(output_path),
        config=job.render_config,
        gpu_info=gpu_info,
        progress_callback=sync_callback,
        ffmpeg_bin=CONFIG.get("ffmpeg_path", "ffmpeg"),
        ffprobe_bin=CONFIG.get("ffprobe_path", "ffprobe"),
    )

    if success and output_path.exists():
        from server.services.file_validator import calculate_checksum
        job.status = STATUS_COMPLETED
        job.output_filename = output_filename
        job.output_size = output_path.stat().st_size
        job.processing_duration = duration
        job.execution_device = execution_device
        # Calculate output checksum
        try:
            job.output_checksum = calculate_checksum(str(output_path))
        except Exception:
            pass
        logger.info(f"Job {job.job_id} completed: {output_filename} "
                    f"({job.output_size} bytes) in {duration:.2f}s")
    else:
        job.status = STATUS_FAILED
        job.error_message = "FFmpeg rendering failed"
        logger.error(f"Job {job.job_id} failed")

    return job
