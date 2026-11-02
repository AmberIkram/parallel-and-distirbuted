# client/networking/websocket_client.py
# WebSocket client for receiving real-time rendering progress updates.

import asyncio
import json
import threading
from typing import Callable, Optional
import websockets  # type: ignore
from client.utils.logger import get_logger

logger = get_logger("websocket_client")


class ProgressWebSocketClient:
    """
    Connects to the server's WebSocket progress endpoint and calls
    the provided callback whenever a progress update arrives.

    Runs in a background daemon thread so it never blocks the GUI.
    """

    def __init__(
        self,
        server_ip: str,
        port: int,
        job_id: str,
        on_progress: Callable[[dict], None],
        on_error: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[dict], None]] = None,
    ):
        self._url = f"ws://{server_ip}:{port}/ws/progress/{job_id}"
        self._job_id = job_id
        self._on_progress = on_progress
        self._on_error = on_error
        self._on_complete = on_complete
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._listen())
        except Exception as e:
            logger.error(f"WebSocket thread error: {e}")
            if self._on_error:
                self._on_error(str(e))
        finally:
            loop.close()

    async def _listen(self):
        reconnect_attempts = 0
        max_reconnects = 5

        while not self._stop_event.is_set() and reconnect_attempts <= max_reconnects:
            try:
                async with websockets.connect(
                    self._url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    reconnect_attempts = 0
                    logger.info(f"WebSocket connected: {self._url}")
                    async for message in ws:
                        if self._stop_event.is_set():
                            break
                        try:
                            data = json.loads(message)
                            if data.get("heartbeat"):
                                continue
                            status = data.get("status", "")
                            if status == "completed":
                                self._on_progress(data)
                                if self._on_complete:
                                    self._on_complete(data)
                                return
                            elif status == "failed":
                                if self._on_error:
                                    self._on_error(data.get("message", "Render failed"))
                                return
                            else:
                                self._on_progress(data)
                        except json.JSONDecodeError:
                            pass

            except (websockets.exceptions.ConnectionClosed,
                    websockets.exceptions.InvalidURI,
                    ConnectionRefusedError, OSError) as e:
                if self._stop_event.is_set():
                    return
                reconnect_attempts += 1
                wait = min(2 ** reconnect_attempts, 30)
                logger.warning(f"WS disconnected: {e}. Retrying in {wait}s "
                               f"(attempt {reconnect_attempts}/{max_reconnects})")
                await asyncio.sleep(wait)

        if reconnect_attempts > max_reconnects:
            msg = "WebSocket reconnection limit reached"
            logger.error(msg)
            if self._on_error:
                self._on_error(msg)
