# tests/test_api.py
# Tests for the FastAPI server endpoints using httpx TestClient.
# These run without a GPU or network connection.

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def client():
    """Create a FastAPI test client."""
    from fastapi.testclient import TestClient
    from server.main import app
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "online"
    assert "version" in body
    assert "gpu_info" in body


def test_handshake_hello(client):
    r = client.post("/handshake", json={
        "message": "HELLO",
        "client_version": "1.0.0"
    })
    assert r.status_code == 200
    body = r.json()
    assert body["message"] == "SERVER_READY"
    assert "gpu_info" in body
    assert "server_version" in body


def test_handshake_wrong_message(client):
    r = client.post("/handshake", json={
        "message": "WRONG",
        "client_version": "1.0.0"
    })
    assert r.status_code == 400


def test_ping(client):
    import time
    t = time.time()
    r = client.post("/ping", json={"message": "PING", "timestamp": t})
    assert r.status_code == 200
    body = r.json()
    assert body["message"] == "PONG"
    assert body["client_timestamp"] == t


def test_gpu_info(client):
    r = client.get("/gpu/info")
    assert r.status_code == 200
    body = r.json()
    assert "available" in body
    assert "cuda_available" in body
    assert "execution_mode" in body
    # Must be one of the valid modes
    assert body["execution_mode"] in ("NVENC", "CUDA", "CPU")


def test_upload_invalid_extension(client):
    import io
    r = client.post(
        "/upload",
        data={"checksum": "0" * 64},
        files={"file": ("malicious.exe", io.BytesIO(b"fake"), "application/octet-stream")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert "extension" in body["message"].lower()


def test_job_not_found(client):
    r = client.get("/jobs/nonexistent-job-id")
    assert r.status_code == 404


def test_list_jobs(client):
    r = client.get("/jobs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_tensor_computation(client):
    r = client.post("/tensor", json={
        "rows_a": 64, "cols_a": 64, "cols_b": 64, "execution_mode": "cpu"
    })
    assert r.status_code == 200
    body = r.json()
    assert "computation_time_ms" in body
    assert body["computation_time_ms"] > 0
    assert "execution_device" in body
