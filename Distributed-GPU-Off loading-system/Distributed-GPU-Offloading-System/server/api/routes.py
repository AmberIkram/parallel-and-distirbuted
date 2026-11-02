# server/api/routes.py
# All FastAPI HTTP and WebSocket route definitions.

import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter, UploadFile, File, Form, Header, HTTPException,
    WebSocket, BackgroundTasks, Depends
)
from fastapi.responses import FileResponse

from shared.models import (
    HandshakeRequest, HandshakeResponse,
    PingRequest, PongResponse,
    JobSubmitRequest, JobStatus,
    HealthResponse, TensorJobRequest, TensorJobResult,
    FileValidation, GPUInfo
)
from shared.constants import (
    APP_NAME, APP_VERSION, STATUS_QUEUED,
    MSG_SERVER_READY, MSG_PONG
)
from shared.protocol import PROTOCOL_VERSION
from server.engine.gpu_detector import get_gpu_info
from server.services.file_validator import (
    safe_filename, validate_uploaded_file, calculate_checksum
)
from server.services.task_manager import (
    create_job, get_job, list_jobs, cancel_job, get_stats
)
from server.services.queue_manager import enqueue_job, request_cancel
from server.api.websocket import websocket_progress_endpoint
from server.utils.config import CONFIG
from server.utils.logger import get_logger

logger = get_logger("routes")
router = APIRouter()
_server_start_time = time.time()


def _check_auth(authorization: Optional[str] = Header(default=None)):
    """Simple token-based auth. Token is in config.json."""
    token = CONFIG.get("auth_token", "")
    if not token or token == "changeme-secret-token":
        return  # Auth disabled or using default — warn but allow
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")


# ── Health ──────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health():
    gpu = get_gpu_info()
    stats = await get_stats()
    return HealthResponse(
        status="online",
        server_name=CONFIG.get("server_name", "GPU-Worker-Node"),
        version=APP_VERSION,
        uptime_seconds=time.time() - _server_start_time,
        gpu_info=gpu.model_dump(),
        active_jobs=stats["processing"],
        queued_jobs=stats["queued"],
        completed_jobs=stats["completed"],
    )


# ── Handshake ────────────────────────────────────────────────────────────────

@router.post("/handshake", response_model=HandshakeResponse)
async def handshake(req: HandshakeRequest):
    if req.message != "HELLO":
        raise HTTPException(status_code=400, detail="Expected HELLO message")
    gpu = get_gpu_info()
    return HandshakeResponse(
        message=MSG_SERVER_READY,
        server_name=CONFIG.get("server_name", "GPU-Worker-Node"),
        server_version=APP_VERSION,
        gpu_info=gpu.model_dump(),
        protocol_version=PROTOCOL_VERSION,
    )


@router.post("/ping", response_model=PongResponse)
async def ping(req: PingRequest):
    return PongResponse(
        message=MSG_PONG,
        server_timestamp=time.time(),
        client_timestamp=req.timestamp,
    )


# ── GPU Info ─────────────────────────────────────────────────────────────────

@router.get("/gpu/info", response_model=GPUInfo)
async def gpu_info(_=Depends(_check_auth)):
    return get_gpu_info()


# ── File Upload ───────────────────────────────────────────────────────────────

@router.post("/upload", response_model=FileValidation)
async def upload_file(
    file: UploadFile = File(...),
    checksum: str = Form(...),
    _=Depends(_check_auth),
):
    upload_dir = Path(CONFIG.get("upload_dir", "uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)

    original_name = safe_filename(file.filename or "upload.mp4")
    # Unique name to avoid collisions
    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    save_path = upload_dir / unique_name

    # Stream the file to disk
    max_bytes = int(CONFIG.get("max_upload_size_mb", 2048)) * 1024 * 1024
    written = 0
    try:
        with open(save_path, "wb") as f:
            while True:
                chunk = await file.read(65536)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    save_path.unlink(missing_ok=True)
                    raise HTTPException(413, "File too large")
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Upload failed: {e}")

    # Validate
    valid, msg = validate_uploaded_file(str(save_path), checksum, original_name)
    if not valid:
        save_path.unlink(missing_ok=True)
        return FileValidation(
            filename=unique_name,
            file_size=written,
            checksum=checksum,
            valid=False,
            message=msg,
        )

    actual_checksum = calculate_checksum(str(save_path))
    logger.info(f"Uploaded: {unique_name} | {written} bytes | checksum OK")
    return FileValidation(
        filename=unique_name,
        file_size=written,
        checksum=actual_checksum,
        valid=True,
        message="Upload successful",
    )


# ── Job Submission ────────────────────────────────────────────────────────────

@router.post("/jobs", response_model=JobStatus)
async def submit_job(req: JobSubmitRequest, _=Depends(_check_auth)):
    # Verify the uploaded file exists
    upload_dir = Path(CONFIG.get("upload_dir", "uploads"))
    file_path = upload_dir / req.input_filename
    if not file_path.exists():
        raise HTTPException(404, f"Uploaded file not found: {req.input_filename}")

    job = await create_job(
        job_id=req.job_id,
        input_filename=req.input_filename,
        file_size=req.file_size,
        render_config=req.render_config,
    )

    await enqueue_job(req.job_id)
    logger.info(f"Job submitted: {req.job_id}")
    return job


# ── Job Status & List ─────────────────────────────────────────────────────────

@router.get("/jobs", response_model=list[JobStatus])
async def list_all_jobs(_=Depends(_check_auth)):
    return await list_jobs()


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str, _=Depends(_check_auth)):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_job_endpoint(job_id: str, _=Depends(_check_auth)):
    request_cancel(job_id)
    cancelled = await cancel_job(job_id)
    if not cancelled:
        raise HTTPException(400, "Job cannot be cancelled (not running or already done)")
    return {"cancelled": True, "job_id": job_id}


# ── Download ──────────────────────────────────────────────────────────────────

@router.get("/download/{job_id}")
async def download_output(job_id: str, _=Depends(_check_auth)):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "completed":
        raise HTTPException(400, f"Job not completed (status: {job.status})")
    if not job.output_filename:
        raise HTTPException(404, "Output file not available")

    output_dir = Path(CONFIG.get("output_dir", "outputs"))
    file_path = output_dir / job.output_filename
    if not file_path.exists():
        raise HTTPException(404, "Output file missing from server")

    return FileResponse(
        path=str(file_path),
        filename=job.output_filename,
        media_type="application/octet-stream",
    )


# ── Optional Tensor Computation ───────────────────────────────────────────────

@router.post("/tensor", response_model=TensorJobResult)
async def tensor_compute(req: TensorJobRequest, _=Depends(_check_auth)):
    from server.engine.cuda_engine import run_tensor_computation
    # Run in thread pool to avoid blocking the event loop
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, run_tensor_computation, req)
    return result


# ── WebSocket Progress ────────────────────────────────────────────────────────

@router.websocket("/ws/progress/{job_id}")
async def ws_progress(job_id: str, websocket: WebSocket):
    await websocket_progress_endpoint(job_id, websocket)
