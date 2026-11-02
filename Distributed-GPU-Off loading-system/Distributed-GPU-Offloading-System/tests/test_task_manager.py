# tests/test_task_manager.py
# Tests for the in-memory task manager (no network required).

import os
import sys
import asyncio
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import RenderConfig
from shared.constants import STATUS_QUEUED, STATUS_PROCESSING, STATUS_CANCELLED


# Reset the job store between tests
@pytest.fixture(autouse=True)
def reset_jobs():
    import server.services.task_manager as tm
    tm._jobs.clear()


def test_create_job():
    from server.services.task_manager import create_job, get_job
    config = RenderConfig()
    job = asyncio.run(create_job("job-001", "video.mp4", 1024, config))
    assert job.job_id == "job-001"
    assert job.status == STATUS_QUEUED
    assert job.progress == 0.0


def test_get_missing_job():
    from server.services.task_manager import get_job
    job = asyncio.run(get_job("does-not-exist"))
    assert job is None


def test_update_progress():
    from server.services.task_manager import create_job, update_job_progress, get_job
    config = RenderConfig()
    asyncio.run(create_job("job-002", "video.mp4", 2048, config))
    asyncio.run(update_job_progress("job-002", 55.0, STATUS_PROCESSING))
    job = asyncio.run(get_job("job-002"))
    assert job.progress == 55.0
    assert job.status == STATUS_PROCESSING


def test_cancel_queued_job():
    from server.services.task_manager import create_job, cancel_job, get_job
    config = RenderConfig()
    asyncio.run(create_job("job-003", "video.mp4", 512, config))
    cancelled = asyncio.run(cancel_job("job-003"))
    assert cancelled
    job = asyncio.run(get_job("job-003"))
    assert job.status == STATUS_CANCELLED


def test_cancel_completed_job_fails():
    from server.services.task_manager import create_job, complete_job, cancel_job, get_job
    from shared.constants import STATUS_COMPLETED

    async def _run():
        config = RenderConfig()
        job = await create_job("job-004", "video.mp4", 512, config)
        job.status = STATUS_COMPLETED
        await complete_job("job-004", job)
        return await cancel_job("job-004")

    cancelled = asyncio.run(_run())
    assert not cancelled


def test_stats():
    from server.services.task_manager import create_job, get_stats

    async def _run():
        config = RenderConfig()
        await create_job("job-s1", "a.mp4", 100, config)
        await create_job("job-s2", "b.mp4", 200, config)
        return await get_stats()

    stats = asyncio.run(_run())
    assert stats["queued"] == 2
    assert stats["total"] == 2


def test_list_jobs():
    from server.services.task_manager import create_job, list_jobs

    async def _run():
        config = RenderConfig()
        await create_job("job-l1", "a.mp4", 100, config)
        await create_job("job-l2", "b.mp4", 200, config)
        return await list_jobs()

    jobs = asyncio.run(_run())
    assert len(jobs) == 2
