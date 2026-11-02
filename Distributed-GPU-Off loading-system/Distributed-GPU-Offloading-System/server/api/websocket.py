# server/api/websocket.py
# WebSocket connection manager for streaming real-time progress to clients.

import asyncio
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from shared.models import ProgressUpdate
from server.utils.logger import get_logger

logger = get_logger("websocket")

# job_id -> set of connected WebSocket clients
_connections: Dict[str, Set[WebSocket]] = {}
_lock = asyncio.Lock()


async def connect(job_id: str, websocket: WebSocket):
    await websocket.accept()
    async with _lock:
        if job_id not in _connections:
            _connections[job_id] = set()
        _connections[job_id].add(websocket)
    logger.info(f"WS client connected for job {job_id}")


async def disconnect(job_id: str, websocket: WebSocket):
    async with _lock:
        if job_id in _connections:
            _connections[job_id].discard(websocket)
            if not _connections[job_id]:
                del _connections[job_id]
    logger.info(f"WS client disconnected for job {job_id}")


async def broadcast_progress(
    job_id: str,
    progress: float,
    status: str,
    message: str,
    execution_device: str = "CPU",
    elapsed_seconds: float = None,
    eta_seconds: float = None,
):
    """Send a progress update to all WebSocket clients watching a job."""
    update = ProgressUpdate(
        job_id=job_id,
        progress=progress,
        status=status,
        message=message,
        execution_device=execution_device,
        elapsed_seconds=elapsed_seconds,
        eta_seconds=eta_seconds,
    )
    payload = update.model_dump_json()

    async with _lock:
        clients = set(_connections.get(job_id, set()))

    dead: list[WebSocket] = []
    for ws in clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)

    if dead:
        async with _lock:
            for ws in dead:
                _connections.get(job_id, set()).discard(ws)


async def websocket_progress_endpoint(job_id: str, websocket: WebSocket):
    """FastAPI endpoint handler for /ws/progress/{job_id}."""
    await connect(job_id, websocket)
    try:
        while True:
            # Keep connection alive — client may send pings
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send a heartbeat to keep the connection alive
                try:
                    await websocket.send_text('{"heartbeat": true}')
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await disconnect(job_id, websocket)
