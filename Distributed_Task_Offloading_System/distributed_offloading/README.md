# Custom Distributed Task Offloading & Remote GPU Rendering System

CSC-334 — Parallel and Distributed Computing

This project implements the assignment as a Python client/server system. The client provides a desktop GUI for job configuration and monitoring; the worker daemon accepts jobs over TCP, validates the upload with SHA-256, renders using FFmpeg, streams progress, and returns the rendered output.

## Repository structure

```text
client/                 Desktop client GUI
server/                 Remote worker daemon and worker_data/
common/                 Framed JSON + file-transfer protocol
benchmarks/             Benchmark generator and CSV results
assets/screenshots/     Execution screenshots
assets/demo_output/    Demo output files
logs/                   Runtime log location
requirements.txt        Optional GUI dependencies
```

## 1. Environment

- Python 3.10+
- FFmpeg available on PATH
- Windows, Linux, or macOS
- For the intended hardware-accelerated deployment: NVIDIA GPU + working NVIDIA driver + FFmpeg built with `h264_nvenc`

The worker automatically checks `nvidia-smi` and FFmpeg encoders. If NVENC is unavailable, it uses `libx264` as a safe development fallback. The protocol and application remain unchanged.

## 2. Network configuration

For a direct LAN setup, configure static IPv4 addresses such as:

- Worker: `192.168.1.1`
- Client: `192.168.1.2`
- Subnet mask: `255.255.255.0`
- TCP port: `5050`

On a single-machine demo, use `127.0.0.1` as the server IP.

## 3. Start the worker

```bash
cd server
python daemon.py --host 0.0.0.0 --port 5050
```

The terminal reports whether NVIDIA/NVENC was detected.

## 4. Start the client

From the project root:

```bash
python client/app.py
```

Enter the worker IP and port, choose a video, select resolution/bitrate/preset, press **CHECK CONNECTION**, then **SUBMIT REMOTE JOB**.

## 5. Protocol and robustness

1. TCP connection is established.
2. Worker sends a protocol-version handshake.
3. Client responds with its handshake and receives an acknowledgement.
4. Client sends job metadata including file size and SHA-256.
5. Worker receives the binary file and validates its checksum.
6. Worker renders with `h264_nvenc` when available; otherwise `libx264`.
7. Progress messages are streamed asynchronously.
8. Worker sends output metadata and the output file.
9. Client saves the returned file under `client/client_output/`.
10. Socket failures and invalid transfers are reported without silently accepting corrupted data.

## 6. Benchmarking

Run:

```bash
python benchmarks/benchmark.py
```

The script creates reproducible FFmpeg test clips at 360p, 720p, and 1080p and writes `benchmark_results.csv`. For a formal real-network comparison, run the same cases with the worker on the second machine and record transfer time, render time, total remote time, and speedup.

## 7. Demo evidence

The `assets/screenshots/` directory contains the captured client/worker execution views included with the submission package.

## 8. Security notes

This is a course prototype intended for a trusted LAN. Production deployment should add authentication, encryption/TLS, job authorization, rate limits, and sandboxing around FFmpeg input handling.
