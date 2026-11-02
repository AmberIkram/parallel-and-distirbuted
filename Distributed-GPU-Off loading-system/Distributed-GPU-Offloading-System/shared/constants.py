# shared/constants.py
# Shared constants used by both client and server

APP_NAME = "Distributed GPU Offloading System"
APP_VERSION = "1.0.0"
APP_SUBTITLE = "Remote Rendering & Computational Task Manager"

# Protocol messages
MSG_HELLO = "HELLO"
MSG_SERVER_READY = "SERVER_READY"
MSG_PING = "PING"
MSG_PONG = "PONG"

# Default network settings
DEFAULT_SERVER_IP = "192.168.1.1"
DEFAULT_CLIENT_IP = "192.168.1.2"
DEFAULT_PORT = 8000
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_UPLOAD_TIMEOUT = 300  # seconds
DEFAULT_DOWNLOAD_TIMEOUT = 300  # seconds
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MB

# File constraints
MAX_UPLOAD_SIZE_MB = 2048  # 2 GB default
ALLOWED_INPUT_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v"}
ALLOWED_OUTPUT_FORMATS = ["mp4", "mkv", "mov"]

# Encoding options
RESOLUTIONS = ["Original", "1080p", "720p", "480p"]
PRESETS = ["fast", "medium", "slow"]
BITRATES = ["2M", "4M", "6M", "8M", "custom"]
OUTPUT_FORMATS = ["mp4", "mkv", "mov"]

# Job statuses
STATUS_QUEUED = "queued"
STATUS_UPLOADING = "uploading"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

# Execution modes
MODE_AUTO = "auto"
MODE_GPU = "gpu"
MODE_CPU = "cpu"

# WebSocket events
WS_EVENT_PROGRESS = "progress"
WS_EVENT_STATUS = "status"
WS_EVENT_LOG = "log"
WS_EVENT_COMPLETE = "complete"
WS_EVENT_ERROR = "error"

# API endpoints
API_HEALTH = "/health"
API_HANDSHAKE = "/handshake"
API_PING = "/ping"
API_UPLOAD = "/upload"
API_JOBS = "/jobs"
API_JOB_STATUS = "/jobs/{job_id}"
API_JOB_CANCEL = "/jobs/{job_id}/cancel"
API_DOWNLOAD = "/download/{job_id}"
API_GPU_INFO = "/gpu/info"
API_TENSOR = "/tensor"
WS_PROGRESS = "/ws/progress/{job_id}"
