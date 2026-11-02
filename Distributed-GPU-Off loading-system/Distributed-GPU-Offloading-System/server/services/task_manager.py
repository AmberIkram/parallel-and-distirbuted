# server/services/task_manager.py
# Central job registry: stores all jobs in memory with thread-safe access.

import asyncio
from datetime import datetime, timezone
from typing import Optional
from shared.models import JobStatus, RenderConfig
from shared.constants import (
    STATUS_QUEUED, STATUS_PROCESSING, STATUS_COMPLETED,
    STATUS_FAILED, STATUS_CANCELLED
)
from server.utils.logger import get_logger

logger = get_logger("task_manager")

# In-memory job store: {job_id: JobStatus}
_jobs: dict[str, JobStatus] = {}
_lock = asyncio.Lock()


async def create_job(
    job_id: str,
    input_filename: str,
    file_size: int,
    render_config: RenderConfig,
) -> JobStatus:
    async with _lock:
        job = JobStatus(
            job_id=job_id,
            input_filename=input_filename,
            file_size=file_size,
            render_config=render_config,
            status=STATUS_QUEUED,
            progress=0.0,
            submitted_at=datetime.now(timezone.utc).isoformat(),
        )
        _jobs[job_id] = job
        logger.info(f"Job created: {job_id} | {input_filename}")
        return job


async def get_job(job_id: str) -> Optional[JobStatus]:
    async with _lock:
        return _jobs.get(job_id)


async def update_job_progress(job_id: str, progress: float, status: str = STATUS_PROCESSING):
    async with _lock:
        job = _jobs.get(job_id)
        if job:
            job.progress = progress
            job.status = status
            if status == STATUS_PROCESSING and job.started_at is None:
                job.started_at = datetime.now(timezone.utc).isoformat()


async def complete_job(job_id: str, updated_job: JobStatus):
    async with _lock:
        updated_job.completed_at = datetime.now(timezone.utc).isoformat()
        _jobs[job_id] = updated_job
        logger.info(f"Job completed: {job_id} | status={updated_job.status}")


async def cancel_job(job_id: str) -> bool:
    async with _lock:
        job = _jobs.get(job_id)
        if job and job.status in (STATUS_QUEUED, STATUS_PROCESSING):
            job.status = STATUS_CANCELLED
            logger.info(f"Job cancelled: {job_id}")
            return True
        return False


async def list_jobs() -> list[JobStatus]:
    async with _lock:
        return list(_jobs.values())


async def get_stats() -> dict:
    async with _lock:
        statuses = [j.status for j in _jobs.values()]
        return {
            "total": len(_jobs),
            "queued": statuses.count(STATUS_QUEUED),
            "processing": statuses.count(STATUS_PROCESSING),
            "completed": statuses.count(STATUS_COMPLETED),
            "failed": statuses.count(STATUS_FAILED),
            "cancelled": statuses.count(STATUS_CANCELLED),
        }
