# tests/test_connection.py
# Tests for the connection manager and API client (requires a running server).
# Mark live tests with @pytest.mark.integration — skip them without --integration flag.

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.networking.connection_manager import base_url, ws_url, load_connection_config


def test_base_url_format():
    url = base_url("192.168.1.1", 8000)
    assert url == "http://192.168.1.1:8000"


def test_ws_url_format():
    url = ws_url("192.168.1.1", 8000, "test-job-id")
    assert url == "ws://192.168.1.1:8000/ws/progress/test-job-id"


def test_load_connection_config_defaults():
    cfg = load_connection_config()
    assert "server_ip" in cfg
    assert "server_port" in cfg
    assert isinstance(cfg["server_port"], int)


@pytest.mark.integration
def test_health_endpoint(live_server_url):
    """Requires --integration and a running server."""
    import httpx
    r = httpx.get(f"{live_server_url}/health", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "online"
    assert "gpu_info" in data


@pytest.mark.integration
def test_handshake(live_server_url):
    from client.networking.api_client import APIClient
    ip, port = live_server_url.replace("http://", "").split(":")
    api = APIClient(ip, int(port))
    hs = api.handshake()
    assert hs.message == "SERVER_READY"
    assert hs.server_version


@pytest.mark.integration
def test_ping_latency(live_server_url):
    from client.networking.api_client import APIClient
    ip, port = live_server_url.replace("http://", "").split(":")
    api = APIClient(ip, int(port))
    pong, rtt = api.ping()
    assert pong.message == "PONG"
    assert rtt > 0
    assert rtt < 5000  # Under 5 seconds on LAN
