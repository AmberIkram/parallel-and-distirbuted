# server/main.py
# FastAPI application entry point.
# Run with: python server/main.py

import sys
import os

# Ensure project root is on path when running as: python server/main.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api.routes import router
from server.engine.gpu_detector import refresh_gpu_info
from server.services.queue_manager import start_workers
from server.utils.config import CONFIG
from server.utils.logger import get_logger
from shared.constants import APP_NAME, APP_VERSION

logger = get_logger("server.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup/shutdown tasks."""
    logger.info(f"{'='*60}")
    logger.info(f"  {APP_NAME} v{APP_VERSION}")
    logger.info(f"  Server starting...")
    logger.info(f"{'='*60}")

    # Detect hardware capabilities
    gpu_info = refresh_gpu_info()
    logger.info(f"  GPU Available : {gpu_info.available}")
    logger.info(f"  GPU Name      : {gpu_info.gpu_name or 'N/A'}")
    logger.info(f"  VRAM          : {gpu_info.vram_mb or 'N/A'} MB")
    logger.info(f"  CUDA          : {gpu_info.cuda_available}")
    logger.info(f"  NVENC         : {gpu_info.nvenc_available}")
    logger.info(f"  FFmpeg        : {gpu_info.ffmpeg_available} ({gpu_info.ffmpeg_version})")
    logger.info(f"  Execution Mode: {gpu_info.execution_mode}")
    logger.info(f"{'='*60}")

    # Start background render workers
    await start_workers()

    yield  # Server is running

    logger.info("Server shutting down...")


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Remote GPU/CPU video rendering server",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    host = CONFIG.get("server_ip", "0.0.0.0")
    port = int(CONFIG.get("server_port", 8000))
    logger.info(f"Listening on {host}:{port}")
    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        reload=False,
        log_level=CONFIG.get("log_level", "info").lower(),
    )
