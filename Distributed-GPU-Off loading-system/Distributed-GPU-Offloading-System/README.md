# Distributed GPU Offloading System

**Remote Rendering & Computational Task Manager**

A distributed computing system that offloads computationally expensive video rendering from a resource-constrained laptop to a powerful remote GPU workstation over a local network.

*CSC-334 Parallel and Distributed Computing — BS Software Engineering*

---

## Problem Statement

Low-end laptops with integrated or limited GPUs cannot efficiently transcode high-resolution video. This system allows the laptop to delegate that work to a remote workstation with an NVIDIA GPU, receive the processed output, and verify its integrity — all through a modern desktop application.

---

## Features

- Modern dark CustomTkinter dashboard
- Real-time WebSocket progress streaming from FFmpeg
- NVIDIA GPU/NVENC detection — CPU fallback when unavailable
- SHA-256 checksum verification at every transfer boundary
- Full job lifecycle: queued → uploading → processing → completed
- Job cancellation and recovery after reconnection
- Optional CUDA tensor computation demo (PyTorch)
- Benchmarking: local CPU vs remote GPU/CPU with charts
- Configurable via `config.json` — no source code edits needed
- Windows batch scripts for one-click setup and launch

---

## System Architecture

```
CLIENT (laptop)                         SERVER (workstation)
  CustomTkinter GUI                       FastAPI + Uvicorn
  httpx REST client          LAN          GPU Detector
  WebSocket client    ──────────────▶     FFmpeg Engine
  File services       ◀──────────────     Task Queue
  SHA-256 checksum                        WebSocket Progress
```

See `docs/architecture.md` for a detailed diagram and communication flow.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Client GUI | CustomTkinter, Tkinter |
| HTTP Client | httpx |
| WebSocket Client | websockets |
| Server Framework | FastAPI |
| Server Runtime | Uvicorn |
| Video Rendering | FFmpeg (NVENC / libx264) |
| GPU Detection | nvidia-smi, PyTorch (optional) |
| System Monitoring | psutil |
| Checksums | hashlib (SHA-256) |
| Data Models | Pydantic v2 |
| Testing | pytest |
| Charts | matplotlib (optional) |

---

## Hardware Requirements

**Client (minimum):**
- Windows 10/11
- Python 3.11+
- 4 GB RAM
- 1 GB free disk space
- Network adapter (Ethernet or Wi-Fi)

**Server (recommended):**
- Windows 10/11 or Linux
- Python 3.11+
- NVIDIA GPU with 4+ GB VRAM (optional but recommended)
- NVIDIA drivers 520+ (for NVENC)
- FFmpeg with NVENC support
- 8 GB RAM
- Gigabit Ethernet adapter

---

## Software Requirements

- Python 3.11 or newer
- FFmpeg (both machines for benchmarking; server machine for rendering)
- NVIDIA CUDA Toolkit (optional, for GPU acceleration)
- PyTorch with CUDA (optional, for tensor demo)

---

## Installation

### Quick Start (Windows)

1. Clone or extract the project:
   ```cmd
   git clone https://github.com/yourusername/distributed-gpu-offloading.git
   cd Distributed-GPU-Offloading-System
   ```

2. Run the setup script (creates venv, installs dependencies):
   ```cmd
   setup.bat
   ```

### Manual Setup

```powershell
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create required directories
mkdir uploads, outputs, logs, benchmarks\results
```

### FFmpeg Installation

Download FFmpeg from https://ffmpeg.org/download.html (Windows builds at https://www.gyan.dev/ffmpeg/builds/)

Extract and add to PATH:
```powershell
# Example: add C:\ffmpeg\bin to system PATH
[System.Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";C:\ffmpeg\bin", "Machine")
```

Verify:
```cmd
ffmpeg -version
```

### NVIDIA CUDA / NVENC

Install NVIDIA drivers from https://www.nvidia.com/drivers

To verify NVENC is available:
```cmd
ffmpeg -encoders | findstr nvenc
```

---

## Network Configuration

See `docs/network_setup.md` for detailed instructions.

**Quick reference (direct Ethernet cable):**

| Computer | IP Address | Subnet Mask |
|----------|-----------|-------------|
| Server | 192.168.1.1 | 255.255.255.0 |
| Client | 192.168.1.2 | 255.255.255.0 |

These are example addresses. Use any addresses in the same subnet that do not conflict with your network.

Open Windows Firewall port (run as Administrator on server):
```powershell
New-NetFirewallRule -DisplayName "GPU Offload Server" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

---

## Configuration

Edit `config.json` to change server settings:

```json
{
  "server_ip": "0.0.0.0",
  "server_port": 8000,
  "server_name": "GPU-Worker-Node",
  "auth_token": "changeme-secret-token",
  "max_upload_size_mb": 2048,
  "worker_concurrency": 1,
  "upload_dir": "uploads",
  "output_dir": "outputs",
  "log_dir": "logs",
  "ffmpeg_path": "ffmpeg",
  "ffprobe_path": "ffprobe"
}
```

**Change the auth_token** to a strong random string before any real deployment.

---

## Running the Application

### Start the Server

On the **server/workstation** computer:

```cmd
run_server.bat
```

Or manually:
```cmd
venv\Scripts\activate
python server/main.py
```

The server prints detected GPU info at startup:
```
GPU Available : True
GPU Name      : NVIDIA GeForce RTX 3060
VRAM          : 12288 MB
CUDA          : True
NVENC         : True
FFmpeg        : True (6.1)
Execution Mode: NVENC
```

### Start the Client

On the **client/laptop** computer:

```cmd
run_client.bat
```

Or manually:
```cmd
venv\Scripts\activate
python client/main.py
```

---

## Submitting a Render Job

1. Enter the server IP address in the **Server Connection** panel
2. Click **Connect** — verify latency and GPU info
3. Click **Browse Video File** and select your video
4. Configure resolution, bitrate, preset, and output format
5. Click **▶ START REMOTE RENDERING**
6. Watch the live progress in the terminal panel
7. Output is saved to the `outputs/` folder

---

## Running Benchmarks

```cmd
# Local only
run_benchmark.bat assets\demo\sample.mp4

# Full comparison (local + remote)
run_benchmark.bat assets\demo\sample.mp4 192.168.1.1

# Multiple files, custom settings
python benchmarks/benchmark.py ^
    --input video1.mp4 video2.mp4 ^
    --server-ip 192.168.1.1 ^
    --resolution 720p ^
    --bitrate 4M ^
    --preset medium
```

Results saved to `benchmarks/results/` as CSV, JSON, and PNG chart.

---

## Running Tests

```cmd
run_tests.bat
```

Or:
```cmd
# Unit tests (no server required)
python -m pytest tests/test_checksum.py tests/test_task_manager.py tests/test_api.py -v

# With integration tests (requires live server)
python -m pytest tests/ -v --integration --server-url http://192.168.1.1:8000
```

---

## Demonstration Workflow

| Step | Action |
|------|--------|
| 1 | Start server on workstation: `run_server.bat` |
| 2 | Observe hardware detection output in console |
| 3 | Launch client on laptop: `run_client.bat` |
| 4 | Enter server IP and click Connect |
| 5 | Verify handshake, latency, and GPU info |
| 6 | Browse and select a sample video file |
| 7 | Configure resolution/bitrate/preset |
| 8 | Click START REMOTE RENDERING |
| 9 | Watch upload progress in log panel |
| 10 | Watch real-time rendering percentage |
| 11 | Verify execution device (NVENC / CPU) in terminal |
| 12 | Wait for download and checksum verification |
| 13 | Click Open Output Folder to inspect result |
| 14 | Run `run_benchmark.bat` for comparison data |
| 15 | Show generated chart in `benchmarks/results/` |

---

## Screenshots to Capture

Take the following screenshots for your submission:

1. **Server startup console** — showing GPU detection results
2. **Client dashboard** — connected state with GPU info populated
3. **File selection** — video selected with file info shown
4. **Upload progress** — progress bar during upload (~30-50%)
5. **Rendering progress** — progress bar at ~50-75%
6. **Completion** — 100% with execution device shown
7. **Output folder** — the rendered file visible
8. **Benchmark results** — the comparison chart PNG

Save screenshots in the `screenshots/` folder.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "FFmpeg not found" | Install FFmpeg and add to PATH; restart terminal |
| "Connection refused" | Check server is running; verify firewall rule |
| "NVENC not available" | Install NVIDIA drivers; test with `ffmpeg -encoders` |
| Upload very slow | Use Ethernet instead of Wi-Fi |
| GUI freezes | Should not happen; file a bug if it does |
| "Checksum mismatch" | Retry; could be a corrupted transfer |
| Port 8000 already in use | Change `server_port` in `config.json` |

---

## Project Structure

```
Distributed-GPU-Offloading-System/
├── client/                 # Desktop application
│   ├── main.py
│   ├── gui/                # CustomTkinter dashboard
│   ├── networking/         # API + WebSocket clients
│   ├── services/           # File, upload, download managers
│   └── utils/              # Checksum, logger
├── server/                 # FastAPI server daemon
│   ├── main.py
│   ├── daemon.py
│   ├── api/                # Routes + WebSocket manager
│   ├── engine/             # GPU detector, FFmpeg, CUDA
│   ├── services/           # Task queue, file validator
│   └── utils/              # Config, logger
├── shared/                 # Pydantic models, protocol, constants
├── benchmarks/             # Benchmark runner + local renderer
├── tests/                  # pytest test suite
├── docs/                   # Architecture, network setup, report
├── assets/                 # Icons, demo files
├── screenshots/            # Capture here for submission
├── uploads/                # Server upload storage
├── outputs/                # Rendered output storage
├── logs/                   # Application logs
├── config.json             # Server/client configuration
├── requirements.txt
├── setup.bat
├── run_server.bat
├── run_client.bat
├── run_benchmark.bat
└── run_tests.bat
```

---

## Limitations

- HTTP/WebSocket only — not encrypted (LAN demo only)
- In-memory job store — jobs lost on server restart
- Single render worker by default (configurable)
- Windows batch scripts only; server works on Linux too

---

## Author

**CSC-334 — Parallel and Distributed Computing**
BS Software Engineering — 7th Semester

---

## License

MIT License — see `LICENSE`
