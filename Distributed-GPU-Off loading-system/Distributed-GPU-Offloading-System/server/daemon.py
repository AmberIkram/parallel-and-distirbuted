# server/daemon.py
# Lightweight wrapper to run the server as a background daemon process.
# On Windows, this runs uvicorn in a subprocess detached from the terminal.

import sys
import os
import subprocess
import time
import signal
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.utils.config import CONFIG

PID_FILE = Path("logs") / "server.pid"


def start():
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            import psutil  # type: ignore
            if psutil.pid_exists(pid):
                print(f"Server already running (PID {pid})")
                return
        except Exception:
            pass

    host = CONFIG.get("server_ip", "0.0.0.0")
    port = int(CONFIG.get("server_port", 8000))

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app",
         "--host", host, "--port", str(port)],
        cwd=Path(__file__).parent.parent,
        stdout=open(Path("logs") / "server_stdout.log", "a"),
        stderr=open(Path("logs") / "server_stderr.log", "a"),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )

    PID_FILE.write_text(str(proc.pid))
    print(f"Server daemon started (PID {proc.pid}) on {host}:{port}")


def stop():
    if not PID_FILE.exists():
        print("No PID file found — server may not be running")
        return
    try:
        pid = int(PID_FILE.read_text().strip())
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink(missing_ok=True)
        print(f"Server stopped (PID {pid})")
    except Exception as e:
        print(f"Could not stop server: {e}")


def status():
    if not PID_FILE.exists():
        print("Server is NOT running")
        return
    try:
        pid = int(PID_FILE.read_text().strip())
        import psutil  # type: ignore
        if psutil.pid_exists(pid):
            print(f"Server is running (PID {pid})")
        else:
            print("Server is NOT running (stale PID file)")
            PID_FILE.unlink(missing_ok=True)
    except Exception as e:
        print(f"Status check error: {e}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "status":
        status()
    else:
        print("Usage: python server/daemon.py [start|stop|status]")
