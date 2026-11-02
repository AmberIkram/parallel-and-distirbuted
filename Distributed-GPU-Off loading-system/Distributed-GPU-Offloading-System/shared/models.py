# shared/models.py
# Pydantic models shared between client and server

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class HandshakeRequest(BaseModel):
    message: str  # "HELLO"
    client_version: str
    client_ip: Optional[str] = None


class HandshakeResponse(BaseModel):
    message: str  # "SERVER_READY"
    server_name: str
    server_version: str
    gpu_info: Dict[str, Any]
    protocol_version: str = "1.0"


class PingRequest(BaseModel):
    message: str = "PING"
    timestamp: float


class PongResponse(BaseModel):
    message: str = "PONG"
    server_timestamp: float
    client_timestamp: float


class RenderConfig(BaseModel):
    resolution: str = "Original"
    bitrate: str = "4M"
    preset: str = "medium"
    output_format: str = "mp4"
    execution_mode: str = "auto"  # auto, gpu, cpu
    custom_bitrate: Optional[str] = None


class JobSubmitRequest(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    input_filename: str
    file_size: int
    input_checksum: str
    render_config: RenderConfig
    submitted_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class JobStatus(BaseModel):
    job_id: str
    input_filename: str
    file_size: int
    render_config: RenderConfig
    status: str
    progress: float = 0.0
    submitted_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output_filename: Optional[str] = None
    output_size: Optional[int] = None
    output_checksum: Optional[str] = None
    error_message: Optional[str] = None
    processing_duration: Optional[float] = None
    execution_device: Optional[str] = None  # "NVENC", "CUDA", "CPU"


class ProgressUpdate(BaseModel):
    job_id: str
    progress: float
    status: str
    message: str
    execution_device: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    eta_seconds: Optional[float] = None


class GPUInfo(BaseModel):
    available: bool
    gpu_name: Optional[str] = None
    vram_mb: Optional[int] = None
    cuda_available: bool = False
    nvenc_available: bool = False
    driver_version: Optional[str] = None
    ffmpeg_available: bool = False
    ffmpeg_version: Optional[str] = None
    execution_mode: str = "CPU"  # "NVENC", "CUDA", "CPU"


class TensorJobRequest(BaseModel):
    rows_a: int = 512
    cols_a: int = 512
    cols_b: int = 512
    execution_mode: str = "auto"


class TensorJobResult(BaseModel):
    execution_device: str
    computation_time_ms: float
    matrix_shape: str
    result_sum: float
    cuda_available: bool


class FileValidation(BaseModel):
    filename: str
    file_size: int
    checksum: str
    valid: bool
    message: str


class HealthResponse(BaseModel):
    status: str
    server_name: str
    version: str
    uptime_seconds: float
    gpu_info: Dict[str, Any]
    active_jobs: int
    queued_jobs: int
    completed_jobs: int
