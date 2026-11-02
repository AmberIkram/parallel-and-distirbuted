# client/networking/api_client.py
# HTTP API client for communicating with the remote server.

import time
import httpx
from typing import Optional, Callable
from pathlib import Path

from shared.models import (
    HandshakeRequest, HandshakeResponse,
    PingRequest, PongResponse,
    JobSubmitRequest, JobStatus,
    RenderConfig, TensorJobRequest, TensorJobResult,
    GPUInfo
)
from shared.constants import (
    APP_VERSION, MSG_HELLO, DEFAULT_TIMEOUT,
    DEFAULT_UPLOAD_TIMEOUT, DEFAULT_DOWNLOAD_TIMEOUT
)
from client.utils.logger import get_logger

logger = get_logger("api_client")


class APIClient:
    def __init__(self, server_ip: str, port: int, auth_token: str = ""):
        self.base_url = f"http://{server_ip}:{port}"
        self.auth_token = auth_token
        self._client = httpx.Client(timeout=DEFAULT_TIMEOUT)

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.auth_token and self.auth_token != "changeme-secret-token":
            h["Authorization"] = f"Bearer {self.auth_token}"
        return h

    def close(self):
        self._client.close()

    # ── Health ────────────────────────────────────────────────────────────

    def health(self) -> dict:
        r = self._client.get(f"{self.base_url}/health", headers=self._headers())
        r.raise_for_status()
        return r.json()

    # ── Handshake ─────────────────────────────────────────────────────────

    def handshake(self) -> HandshakeResponse:
        req = HandshakeRequest(message=MSG_HELLO, client_version=APP_VERSION)
        r = self._client.post(
            f"{self.base_url}/handshake",
            content=req.model_dump_json(),
            headers=self._headers(),
        )
        r.raise_for_status()
        return HandshakeResponse(**r.json())

    def ping(self) -> tuple[PongResponse, float]:
        """Returns (pong_response, round_trip_ms)."""
        t0 = time.time()
        req = PingRequest(message="PING", timestamp=t0)
        r = self._client.post(
            f"{self.base_url}/ping",
            content=req.model_dump_json(),
            headers=self._headers(),
        )
        rtt = (time.time() - t0) * 1000
        r.raise_for_status()
        return PongResponse(**r.json()), rtt

    # ── GPU Info ──────────────────────────────────────────────────────────

    def gpu_info(self) -> GPUInfo:
        r = self._client.get(f"{self.base_url}/gpu/info", headers=self._headers())
        r.raise_for_status()
        return GPUInfo(**r.json())

    # ── Upload ────────────────────────────────────────────────────────────

    def upload_file(
        self,
        file_path: str,
        checksum: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> dict:
        """
        Upload a file with optional progress tracking.
        progress_callback(bytes_sent, total_bytes)
        """
        path = Path(file_path)
        total = path.stat().st_size

        # Build auth headers (no Content-Type — httpx sets it for multipart)
        headers = {}
        if self.auth_token and self.auth_token != "changeme-secret-token":
            headers["Authorization"] = f"Bearer {self.auth_token}"

        with open(file_path, "rb") as f:
            if progress_callback:
                def gen():
                    sent = 0
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        sent += len(chunk)
                        progress_callback(sent, total)
                        yield chunk

                r = self._client.post(
                    f"{self.base_url}/upload",
                    data={"checksum": checksum},
                    files={"file": (path.name, gen(), "application/octet-stream")},
                    headers=headers,
                    timeout=DEFAULT_UPLOAD_TIMEOUT,
                )
            else:
                r = self._client.post(
                    f"{self.base_url}/upload",
                    data={"checksum": checksum},
                    files={"file": (path.name, f, "application/octet-stream")},
                    headers=headers,
                    timeout=DEFAULT_UPLOAD_TIMEOUT,
                )

        r.raise_for_status()
        return r.json()

    # ── Jobs ──────────────────────────────────────────────────────────────

    def submit_job(self, req: JobSubmitRequest) -> JobStatus:
        r = self._client.post(
            f"{self.base_url}/jobs",
            content=req.model_dump_json(),
            headers=self._headers(),
        )
        r.raise_for_status()
        return JobStatus(**r.json())

    def get_job_status(self, job_id: str) -> JobStatus:
        r = self._client.get(
            f"{self.base_url}/jobs/{job_id}",
            headers=self._headers(),
        )
        r.raise_for_status()
        return JobStatus(**r.json())

    def list_jobs(self) -> list[JobStatus]:
        r = self._client.get(f"{self.base_url}/jobs", headers=self._headers())
        r.raise_for_status()
        return [JobStatus(**j) for j in r.json()]

    def cancel_job(self, job_id: str) -> bool:
        r = self._client.post(
            f"{self.base_url}/jobs/{job_id}/cancel",
            headers=self._headers(),
        )
        return r.status_code == 200

    # ── Download ──────────────────────────────────────────────────────────

    def download_output(
        self,
        job_id: str,
        save_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        headers = dict(self._headers())
        headers.pop("Content-Type", None)

        with self._client.stream(
            "GET",
            f"{self.base_url}/download/{job_id}",
            headers=headers,
            timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        ) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            received = 0
            with open(save_path, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)
                    received += len(chunk)
                    if progress_callback and total:
                        progress_callback(received, total)
        return True

    # ── Tensor Computation ────────────────────────────────────────────────

    def tensor_compute(self, req: TensorJobRequest) -> TensorJobResult:
        r = self._client.post(
            f"{self.base_url}/tensor",
            content=req.model_dump_json(),
            headers=self._headers(),
            timeout=120,
        )
        r.raise_for_status()
        return TensorJobResult(**r.json())
