# server/services/queue_manager.py
# Manages job execution queue with configurable concurrency.
# Ensures only N jobs run simultaneously (default: 1).

import asyncio
from typing import Callable
from shared.constants import STATUS_PROCESSING, STATUS_COMPLETED, STATUS_FAILED
from server.utils.config import CONFIG
from server.utils.logger import get_logger
from server.services.task_manager import (
    get_job, update_job_progress, complete_job
)

logger = get_logger("queue_manager")

_queue: asyncio.Queue = asyncio.Queue()
_active_jobs: set[str] = set()
_cancel_flags: dict[str, bool] = {}
_workers_started = False


def request_cancel(job_id: str):
    """Signal a running job to cancel."""
    _cancel_flags[job_id] = True


async def enqueue_job(job_id: str):
    """Add a job to the execution queue."""
    _cancel_flags[job_id] = False
    await _queue.put(job_id)
    logger.info(f"Job enqueued: {job_id} | Queue size: {_queue.qsize()}")


async def _worker():
    """Worker coroutine that processes jobs from the queue."""
    while True:
        job_id = await _queue.get()
        try:
            if _cancel_flags.get(job_id):
                logger.info(f"Job {job_id} was cancelled before execution")
                _queue.task_done()
                continue

            _active_jobs.add(job_id)
            logger.info(f"Worker picked up job: {job_id}")

            job = await get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found in task manager")
                _queue.task_done()
                _active_jobs.discard(job_id)
                continue

            await update_job_progress(job_id, 0.0, STATUS_PROCESSING)

            # Import here to avoid circular imports at module load time
            from server.engine.render_engine import execute_render_job
            from server.api.websocket import broadcast_progress

            def progress_callback(pct: float, msg: str, device: str):
                if _cancel_flags.get(job_id):
                    return
                asyncio.get_event_loop().call_soon_threadsafe(
                    lambda: asyncio.ensure_future(
                        _handle_progress(job_id, pct, msg, device)
                    )
                )

            updated_job = await execute_render_job(job, progress_callback)
            await complete_job(job_id, updated_job)

            # Final progress broadcast
            await broadcast_progress(
                job_id,
                updated_job.progress if updated_job.status == STATUS_COMPLETED else 0.0,
                updated_job.status,
                updated_job.error_message or "Job finished",
                updated_job.execution_device or "CPU",
            )

        except Exception as e:
            logger.exception(f"Worker error on job {job_id}: {e}")
            job = await get_job(job_id)
            if job:
                job.status = STATUS_FAILED
                job.error_message = str(e)
                await complete_job(job_id, job)
        finally:
            _active_jobs.discard(job_id)
            _cancel_flags.pop(job_id, None)
            _queue.task_done()


async def _handle_progress(job_id: str, pct: float, msg: str, device: str):
    from server.api.websocket import broadcast_progress
    await update_job_progress(job_id, pct, STATUS_PROCESSING)
    await broadcast_progress(job_id, pct, STATUS_PROCESSING, msg, device)


async def start_workers():
    """Start background worker tasks. Called once on server startup."""
    global _workers_started
    if _workers_started:
        return
    concurrency = int(CONFIG.get("worker_concurrency", 1))
    for i in range(concurrency):
        asyncio.create_task(_worker())
    _workers_started = True
    logger.info(f"Started {concurrency} render worker(s)")
