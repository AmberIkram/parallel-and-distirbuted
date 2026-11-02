# benchmarks/benchmark.py
# Benchmarking module: compares local CPU vs remote GPU/CPU rendering.
# Run with: python benchmarks/benchmark.py --help

import sys
import os
import time
import csv
import json
import argparse
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psutil  # type: ignore

from client.networking.api_client import APIClient
from client.networking.connection_manager import load_connection_config
from client.services.upload_manager import upload_with_verification
from client.services.download_manager import download_with_verification
from client.utils.checksum import calculate_checksum
from benchmarks.local_renderer import render_locally, ffmpeg_available
from shared.models import RenderConfig, JobSubmitRequest
from shared.constants import STATUS_COMPLETED, STATUS_FAILED

RESULTS_DIR = Path("benchmarks/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Resource Monitoring ────────────────────────────────────────────────────

class ResourceMonitor:
    """Samples CPU and RAM usage in a background thread."""
    def __init__(self, interval: float = 0.5):
        self._interval = interval
        self._running = False
        self._cpu: list[float] = []
        self._ram: list[float] = []
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._running = True
        self._cpu.clear()
        self._ram.clear()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()

    def stop(self) -> dict:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        return {
            "cpu_avg": sum(self._cpu) / len(self._cpu) if self._cpu else 0,
            "cpu_max": max(self._cpu) if self._cpu else 0,
            "ram_mb_avg": sum(self._ram) / len(self._ram) if self._ram else 0,
            "ram_mb_max": max(self._ram) if self._ram else 0,
        }

    def _sample(self):
        while self._running:
            self._cpu.append(psutil.cpu_percent(interval=None))
            self._ram.append(psutil.virtual_memory().used / (1024 * 1024))
            time.sleep(self._interval)


def _nvidia_smi_util() -> Optional[float]:
    """Get GPU utilization % via nvidia-smi, or None."""
    import subprocess, shutil
    if not shutil.which("nvidia-smi"):
        return None
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            return float(r.stdout.strip())
    except Exception:
        pass
    return None


# ── Benchmark Functions ────────────────────────────────────────────────────

def run_local_benchmark(input_path: str, config: RenderConfig) -> dict:
    """Run a local CPU render and collect metrics."""
    print(f"  [LOCAL] Rendering {Path(input_path).name} locally (CPU)...")
    out_path = str(RESULTS_DIR / f"local_bench_{int(time.time())}.{config.output_format}")

    monitor = ResourceMonitor()
    monitor.start()

    success, duration, error = render_locally(
        input_path, out_path,
        resolution=config.resolution,
        bitrate=config.bitrate,
        preset=config.preset,
        output_format=config.output_format,
    )

    resources = monitor.stop()

    result = {
        "type": "local_cpu",
        "input_file": Path(input_path).name,
        "file_size_mb": round(Path(input_path).stat().st_size / (1024*1024), 2),
        "resolution": config.resolution,
        "bitrate": config.bitrate,
        "preset": config.preset,
        "success": success,
        "duration_s": round(duration, 2),
        "error": error,
        "cpu_avg_pct": round(resources["cpu_avg"], 1),
        "cpu_max_pct": round(resources["cpu_max"], 1),
        "ram_mb_avg": round(resources["ram_mb_avg"], 1),
        "gpu_util_pct": "N/A",
        "upload_time_s": 0,
        "download_time_s": 0,
        "network_overhead_s": 0,
        "execution_device": "CPU (local)",
        "output_path": out_path if success else "",
        "timestamp": datetime.now().isoformat(),
    }
    print(f"  [LOCAL] Done in {duration:.2f}s")
    return result


def run_remote_benchmark(
    api: APIClient,
    input_path: str,
    config: RenderConfig,
    server_ip: str,
    server_port: int,
) -> dict:
    """Run a remote render via the API and collect metrics."""
    import uuid
    from client.networking.websocket_client import ProgressWebSocketClient

    print(f"  [REMOTE] Uploading {Path(input_path).name}...")
    job_id = str(uuid.uuid4())
    monitor = ResourceMonitor()
    monitor.start()

    # Upload timing
    upload_start = time.perf_counter()
    ok, server_filename, err = upload_with_verification(api, input_path)
    upload_time = time.perf_counter() - upload_start

    if not ok:
        monitor.stop()
        return {
            "type": "remote",
            "success": False,
            "error": f"Upload failed: {err}",
            "input_file": Path(input_path).name,
            "timestamp": datetime.now().isoformat(),
        }

    print(f"  [REMOTE] Uploaded in {upload_time:.2f}s. Submitting job...")

    checksum = calculate_checksum(input_path)
    req = JobSubmitRequest(
        job_id=job_id,
        input_filename=server_filename,
        file_size=Path(input_path).stat().st_size,
        input_checksum=checksum,
        render_config=config,
    )
    api.submit_job(req)

    # Wait for completion via polling + WebSocket
    render_start = time.perf_counter()
    ws_done = threading.Event()
    gpu_util_samples: list[float] = []
    execution_device = ["CPU"]

    def on_progress(data: dict):
        g = _nvidia_smi_util()
        if g is not None:
            gpu_util_samples.append(g)
        d = data.get("execution_device")
        if d:
            execution_device[0] = d

    def on_complete(_):
        ws_done.set()

    ws = ProgressWebSocketClient(server_ip, server_port, job_id, on_progress, None, on_complete)
    ws.start()

    # Polling fallback
    max_wait = 3600
    waited = 0
    while not ws_done.is_set() and waited < max_wait:
        ws_done.wait(timeout=5)
        waited += 5
        try:
            status = api.get_job_status(job_id)
            if status.status in (STATUS_COMPLETED, STATUS_FAILED):
                ws_done.set()
        except Exception:
            pass

    ws.stop()
    render_time = time.perf_counter() - render_start

    final = api.get_job_status(job_id)
    if final.status != STATUS_COMPLETED:
        resources = monitor.stop()
        return {
            "type": "remote",
            "success": False,
            "error": f"Job failed: {final.error_message}",
            "input_file": Path(input_path).name,
            "timestamp": datetime.now().isoformat(),
        }

    # Download timing
    print(f"  [REMOTE] Render done in {render_time:.2f}s. Downloading...")
    dl_start = time.perf_counter()
    out_path = str(RESULTS_DIR / f"remote_bench_{int(time.time())}.{config.output_format}")
    ok, saved_path, err = download_with_verification(
        api, job_id, config.output_format,
        expected_checksum=final.output_checksum,
    )
    dl_time = time.perf_counter() - dl_start
    resources = monitor.stop()

    total_time = upload_time + render_time + dl_time
    network_overhead = upload_time + dl_time

    gpu_util = round(sum(gpu_util_samples) / len(gpu_util_samples), 1) if gpu_util_samples else "N/A"

    print(f"  [REMOTE] Download done in {dl_time:.2f}s. Total: {total_time:.2f}s")

    return {
        "type": "remote",
        "input_file": Path(input_path).name,
        "file_size_mb": round(Path(input_path).stat().st_size / (1024*1024), 2),
        "resolution": config.resolution,
        "bitrate": config.bitrate,
        "preset": config.preset,
        "success": ok,
        "error": err if not ok else "",
        "upload_time_s": round(upload_time, 2),
        "render_time_s": round(render_time, 2),
        "download_time_s": round(dl_time, 2),
        "total_time_s": round(total_time, 2),
        "network_overhead_s": round(network_overhead, 2),
        "execution_device": execution_device[0],
        "cpu_avg_pct": round(resources["cpu_avg"], 1),
        "cpu_max_pct": round(resources["cpu_max"], 1),
        "ram_mb_avg": round(resources["ram_mb_avg"], 1),
        "gpu_util_pct": gpu_util,
        "output_path": saved_path,
        "processing_duration_s": round(final.processing_duration or 0, 2),
        "timestamp": datetime.now().isoformat(),
    }


# ── CSV & Report ───────────────────────────────────────────────────────────

def save_csv(results: list[dict], path: str):
    if not results:
        return
    fieldnames = sorted(set().union(*[r.keys() for r in results]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"CSV saved: {path}")


def print_table(results: list[dict]):
    """Print a simple comparison table to stdout."""
    print("\n" + "="*80)
    print(f"{'TYPE':<12} {'FILE':<25} {'DEVICE':<12} {'TOTAL(s)':<10} "
          f"{'NET_OH(s)':<10} {'CPU%':<8} {'GPU%':<8}")
    print("-"*80)
    for r in results:
        if not r.get("success"):
            print(f"{'FAILED':<12} {r.get('input_file','?'):<25} "
                  f"{'—':<12} {'—':<10} {'—':<10} {'—':<8} {'—':<8}")
            continue
        rtype    = r.get("type", "?")
        fname    = r.get("input_file", "?")[:24]
        device   = str(r.get("execution_device", "?"))[:11]
        total    = r.get("total_time_s") or r.get("duration_s") or 0
        net      = r.get("network_overhead_s", 0)
        cpu_pct  = r.get("cpu_avg_pct", "?")
        gpu_pct  = r.get("gpu_util_pct", "N/A")
        print(f"{rtype:<12} {fname:<25} {device:<12} {total:<10.2f} "
              f"{net:<10.2f} {str(cpu_pct):<8} {str(gpu_pct):<8}")
    print("="*80 + "\n")


def generate_chart(results: list[dict], output_png: str):
    """Generate a matplotlib comparison chart if matplotlib is available."""
    try:
        import matplotlib.pyplot as plt  # type: ignore
        import matplotlib
        matplotlib.use("Agg")

        labels, durations, colors = [], [], []
        for r in results:
            if not r.get("success"):
                continue
            rtype = r.get("type", "?")
            fname = Path(r.get("input_file", "?")).stem[:12]
            total = r.get("total_time_s") or r.get("duration_s") or 0
            label = f"{fname}\n({rtype})"
            labels.append(label)
            durations.append(total)
            colors.append("#58a6ff" if rtype == "local_cpu" else "#3fb950")

        if not labels:
            return

        fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.5), 5))
        bars = ax.bar(labels, durations, color=colors, edgecolor="#30363d", width=0.5)
        ax.set_ylabel("Time (seconds)", color="#e6edf3")
        ax.set_title("Rendering Time Comparison", color="#e6edf3", fontsize=14)
        ax.set_facecolor("#161b22")
        fig.patch.set_facecolor("#0d1117")
        ax.tick_params(colors="#8b949e")
        ax.spines["bottom"].set_color("#30363d")
        ax.spines["left"].set_color("#30363d")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        for bar, val in zip(bars, durations):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                    f"{val:.1f}s", ha="center", color="#e6edf3", fontsize=9)

        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="#58a6ff", label="Local CPU"),
            Patch(facecolor="#3fb950", label="Remote"),
        ]
        ax.legend(handles=legend_elements, facecolor="#161b22", labelcolor="#e6edf3")

        plt.tight_layout()
        plt.savefig(output_png, dpi=120, bbox_inches="tight")
        plt.close()
        print(f"Chart saved: {output_png}")
    except ImportError:
        print("matplotlib not installed — skipping chart generation")


# ── CLI Entry Point ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark local vs remote rendering"
    )
    parser.add_argument("--input", required=True, nargs="+",
                        help="Input video file(s)")
    parser.add_argument("--server-ip", help="Remote server IP")
    parser.add_argument("--server-port", type=int, default=8000)
    parser.add_argument("--token", default="", help="Auth token")
    parser.add_argument("--resolution", default="Original",
                        choices=["Original", "1080p", "720p", "480p"])
    parser.add_argument("--bitrate", default="4M")
    parser.add_argument("--preset", default="medium",
                        choices=["fast", "medium", "slow"])
    parser.add_argument("--output-format", default="mp4")
    parser.add_argument("--local-only", action="store_true",
                        help="Run local benchmarks only")
    parser.add_argument("--remote-only", action="store_true",
                        help="Run remote benchmarks only")
    args = parser.parse_args()

    config = RenderConfig(
        resolution=args.resolution,
        bitrate=args.bitrate,
        preset=args.preset,
        output_format=args.output_format,
        execution_mode="auto",
    )

    # Determine server connection
    server_ip = args.server_ip
    server_port = args.server_port
    token = args.token

    if not server_ip and not args.local_only:
        cfg = load_connection_config()
        server_ip = cfg.get("server_ip", "")
        server_port = cfg.get("server_port", 8000)
        token = cfg.get("auth_token", "")

    results: list[dict] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    api = None
    if not args.local_only and server_ip:
        try:
            api = APIClient(server_ip, server_port, token)
            api.handshake()
            print(f"Connected to remote server: {server_ip}:{server_port}")
        except Exception as e:
            print(f"Warning: Could not connect to server: {e}")
            print("Running local-only benchmark.")
            api = None

    for input_file in args.input:
        if not Path(input_file).exists():
            print(f"Skipping (not found): {input_file}")
            continue

        print(f"\nBenchmarking: {input_file}")

        if not args.remote_only:
            if ffmpeg_available():
                local_result = run_local_benchmark(input_file, config)
                results.append(local_result)
            else:
                print("  [LOCAL] Skipped — FFmpeg not found")

        if not args.local_only and api:
            remote_result = run_remote_benchmark(api, input_file, config,
                                                  server_ip, server_port)
            results.append(remote_result)

    if not results:
        print("No results collected.")
        return

    # Compute speedup factors
    local_results  = [r for r in results if r.get("type") == "local_cpu" and r.get("success")]
    remote_results = [r for r in results if r.get("type") == "remote" and r.get("success")]

    for lr in local_results:
        for rr in remote_results:
            if lr.get("input_file") == rr.get("input_file"):
                local_t  = lr.get("duration_s", 0)
                remote_t = rr.get("total_time_s", 0)
                if remote_t > 0:
                    speedup = local_t / remote_t
                    print(f"\nSpeedup for {lr['input_file']}: {speedup:.2f}x "
                          f"(local={local_t:.1f}s, remote={remote_t:.1f}s)")

    # Save outputs
    csv_path = str(RESULTS_DIR / f"benchmark_{timestamp}.csv")
    save_csv(results, csv_path)

    chart_path = str(RESULTS_DIR / f"benchmark_{timestamp}.png")
    generate_chart(results, chart_path)

    print_table(results)

    # Save JSON
    json_path = str(RESULTS_DIR / f"benchmark_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"JSON saved: {json_path}")


if __name__ == "__main__":
    main()
