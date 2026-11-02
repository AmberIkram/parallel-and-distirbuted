# server/utils/config.py
# Server configuration loaded from config.json or environment variables

import json
import os
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"

_DEFAULTS = {
    "server_ip": "0.0.0.0",
    "server_port": 8000,
    "server_name": "GPU-Worker-Node",
    "auth_token": "changeme-secret-token",
    "max_upload_size_mb": 2048,
    "worker_concurrency": 1,
    "upload_dir": "uploads",
    "output_dir": "outputs",
    "log_dir": "logs",
    "log_level": "INFO",
    "ffmpeg_path": "ffmpeg",
    "ffprobe_path": "ffprobe"
}


def load_config() -> dict:
    cfg = dict(_DEFAULTS)
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r") as f:
                user_cfg = json.load(f)
            cfg.update(user_cfg)
        except Exception:
            pass
    # Allow env var overrides
    for key in cfg:
        env_key = f"GPU_OFFLOAD_{key.upper()}"
        if env_key in os.environ:
            cfg[key] = os.environ[env_key]
    return cfg


CONFIG = load_config()
