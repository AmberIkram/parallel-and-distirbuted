# Technical Report — Distributed Task Offloading & Remote GPU Rendering

## 1. Objective
The system offloads a compute-heavy video rendering task from a client machine to a remote worker over TCP. The client controls the job through a desktop GUI and receives progress and the rendered file from the worker.

## 2. Architecture
The implementation follows a Client–Server architecture:

**Client GUI → TCP handshake → file upload + SHA-256 → worker queue/render engine → progress stream → output transfer → client verification.**

The worker detects NVIDIA hardware with `nvidia-smi` and checks FFmpeg for `h264_nvenc`. When both are available, NVENC is selected. During development on a machine without NVIDIA hardware, the tested fallback is FFmpeg `libx264`.

## 3. Task 1 — Networking & Handshake (20)
- TCP listener on port 5050.
- Static LAN examples documented as `192.168.1.1` (worker) and `192.168.1.2` (client).
- Protocol version handshake.
- Client latency measurement.
- Connection errors reported in the GUI.

## 4. Task 2 — Remote GPU Execution Engine (25)
- Background worker accepts jobs concurrently using daemon threads.
- Job metadata includes filename, size, resolution, bitrate, preset, and SHA-256.
- FFmpeg execution targets `h264_nvenc` when available.
- CPU `libx264` fallback keeps the demonstration runnable on non-NVIDIA development machines.

## 5. Task 3 — Client GUI (25)
The desktop client includes:
- server IP and TCP port fields;
- input file picker;
- resolution, bitrate, and preset controls;
- connection check;
- live terminal-style logging;
- progress bar and percentage;
- worker/NVENC status;
- latency and integrity status;
- automatic output-file saving.

The code is designed to use a modern GUI package when available, while retaining a standard Tkinter fallback so the project can be demonstrated on a clean Python installation.

## 6. Task 4 — Robustness & Progress (15)
- Progress messages are streamed asynchronously while FFmpeg runs.
- Upload size and SHA-256 are checked before rendering.
- Output SHA-256 is checked after download.
- Socket timeouts and unexpected disconnects become visible job errors.
- Corrupt or incomplete uploads are rejected.

## 7. Task 5 — Benchmarking & Analysis (15)
Three reproducible test clips were generated at 360p, 720p, and 1080p. The benchmark CSV is included in `benchmarks/benchmark_results.csv`.

| Case | Resolution | Local render (s) | Worker-path render (s) | Measured factor |
|---|---:|---:|---:|---:|
| Small | 640×360 | 0.167 | 0.162 | 1.03× |
| Medium | 1280×720 | 0.808 | 0.773 | 1.05× |
| Large | 1920×1080 | 2.461 | 2.899 | 0.85× |

**Important:** these benchmark values are a reproducible single-machine worker-path baseline, not a claim of real network/GPU speedup. A true remote benchmark requires the worker to run on a second machine with the intended NVIDIA GPU and LAN connection. The project is structured so the same client can target that machine by changing the Server IP field.

## 8. Evidence
`assets/screenshots/client_live_progress.png` shows a real execution of the GUI with handshake, upload verification, remote render progress, output transfer, and output checksum verification. `assets/screenshots/demo.gif` contains a short multi-state GUI demonstration. The worker terminal evidence is stored alongside the screenshots.

## 9. Conclusion
The implementation covers the required distributed offloading workflow end-to-end: networking, handshake, file transfer, integrity checking, remote FFmpeg execution, asynchronous progress reporting, output retrieval, and benchmark support. The NVIDIA/NVENC path is ready for execution on a compatible GPU worker, while the CPU fallback allows the complete system to be tested without specialized hardware.
