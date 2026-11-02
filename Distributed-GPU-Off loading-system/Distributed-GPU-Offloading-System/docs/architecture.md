# System Architecture

## Overview

The Distributed GPU Offloading System follows a client-server architecture where a resource-constrained client offloads computationally expensive video rendering tasks to a more powerful remote worker.

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT LAPTOP                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │             CustomTkinter GUI Dashboard             │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐│   │
│  │  │Connection│ │  File    │ │ Rendering Config     ││   │
│  │  │  Panel   │ │ Selector │ │ & Action Panel       ││   │
│  │  └──────────┘ └──────────┘ └──────────────────────┘│   │
│  │  ┌───────────────────────────────────────────────── │   │
│  │  │        Live Progress Terminal (Log Panel)        │   │
│  │  └─────────────────────────────────────────────────┘│   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐  │
│  │  API Client │  │  WS Client  │  │  File Services    │  │
│  │  (httpx)    │  │(websockets) │  │ Upload/Download   │  │
│  └─────────────┘  └─────────────┘  └───────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │  TCP/IP (LAN)
                       │  HTTP REST + WebSocket
                       │  Port 8000
┌──────────────────────┴──────────────────────────────────────┐
│                     REMOTE WORKER                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               FastAPI + Uvicorn                     │   │
│  │  /health  /handshake  /ping  /upload  /jobs         │   │
│  │  /download  /gpu/info  /tensor  /ws/progress        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────┐  ┌──────────────────────────────────┐ │
│  │  Queue Manager  │  │       WebSocket Manager          │ │
│  │  (asyncio)      │  │   (real-time progress streams)   │ │
│  └────────┬────────┘  └──────────────────────────────────┘ │
│           │                                                  │
│  ┌────────▼──────────────────────────────────────────────┐  │
│  │                   Render Engine                       │  │
│  │                                                       │  │
│  │  ┌────────────────┐    ┌─────────────────────────┐   │  │
│  │  │ GPU Detector   │    │    FFmpeg Engine         │   │  │
│  │  │ nvidia-smi     │    │  -c h264_nvenc (GPU)     │   │  │
│  │  │ torch.cuda     │    │  -c libx264   (CPU)      │   │  │
│  │  │ ffmpeg -enc    │    │  -progress pipe:1        │   │  │
│  │  └────────────────┘    └─────────────────────────┘   │  │
│  │                                                       │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  Optional: CUDA Tensor Engine (PyTorch)        │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  File Storage: uploads/  outputs/  logs/             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Communication Workflow

```
CLIENT                                              SERVER
  │                                                   │
  │──── POST /handshake {"message":"HELLO"} ─────────▶│
  │◀─── {"message":"SERVER_READY", gpu_info...} ──────│
  │                                                   │
  │──── POST /ping {"timestamp": t} ─────────────────▶│
  │◀─── {"message":"PONG", ...} ──────────────────────│
  │     [Client calculates RTT]                       │
  │                                                   │
  │──── POST /upload (multipart + checksum) ─────────▶│
  │◀─── {"valid": true, "filename": "uuid_file.mp4"} ─│
  │                                                   │
  │──── POST /jobs {job_id, config, ...} ────────────▶│
  │◀─── JobStatus {status: "queued"} ─────────────────│
  │                                                   │
  │──── WS /ws/progress/{job_id} ────────────────────▶│
  │◀═══ progress updates (JSON stream) ═══════════════│
  │     {"progress": 25.0, "status": "processing"...} │
  │     {"progress": 50.0, ...}                       │
  │     {"progress": 100.0, "status": "completed"}    │
  │                                                   │
  │──── GET /download/{job_id} ──────────────────────▶│
  │◀─── [binary file stream] ─────────────────────────│
  │     [verify checksum locally]                     │
  │                                                   │
```

## Key Design Decisions

**Checksum verification at every boundary** — calculated before upload, verified on the server after receive, verified again after download. This catches any corruption during transfer.

**WebSocket + HTTP polling fallback** — The client connects via WebSocket for live progress but also polls the REST API every few seconds. If the WebSocket drops, the client still gets the final status.

**No shell=True** — All subprocess calls (FFmpeg, nvidia-smi) use argument lists. User input is never interpolated into shell strings.

**CPU fallback is automatic** — GPU detection runs at startup. If NVENC is unavailable, the render engine falls back to libx264 without any manual configuration.

**Job recovery** — Each job has a unique UUID. If the client disconnects, it can reconnect and poll `/jobs/{job_id}` to retrieve the current status and continue monitoring.
