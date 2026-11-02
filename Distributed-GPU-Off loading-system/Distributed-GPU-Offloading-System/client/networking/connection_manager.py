# client/networking/connection_manager.py
# Manages server connection state and configuration.

import json
from pathlib import Path
from shared.constants import DEFAULT_PORT

_CONFIG_PATH = Path("config.json")


def load_connection_config() -> dict:
    """Load server IP/port from config.json if available."""
    defaults = {
        "server_ip": "",
        "server_port": DEFAULT_PORT,
        "auth_token": "changeme-secret-token",
    }
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH) as f:
                data = json.load(f)
            defaults.update({k: data[k] for k in defaults if k in data})
        except Exception:
            pass
    return defaults


def save_connection_config(server_ip: str, server_port: int, auth_token: str = ""):
    """Persist the last used connection settings."""
    existing = {}
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH) as f:
                existing = json.load(f)
        except Exception:
            pass
    existing["server_ip"] = server_ip
    existing["server_port"] = server_port
    if auth_token:
        existing["auth_token"] = auth_token
    with open(_CONFIG_PATH, "w") as f:
        json.dump(existing, f, indent=2)


def base_url(server_ip: str, port: int) -> str:
    return f"http://{server_ip}:{port}"


def ws_url(server_ip: str, port: int, job_id: str) -> str:
    return f"ws://{server_ip}:{port}/ws/progress/{job_id}"
