import argparse, json, os, shutil, socket, subprocess, threading, time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common.protocol import recv_file, recv_json, send_file, send_json, sha256_file, make_handshake

HOST = '0.0.0.0'
PORT = 5050
BASE = Path(__file__).resolve().parent
WORK = BASE / 'worker_data'
INBOX = WORK / 'input'
OUTBOX = WORK / 'output'
INBOX.mkdir(parents=True, exist_ok=True)
OUTBOX.mkdir(parents=True, exist_ok=True)


def gpu_available():
    try:
        r = subprocess.run(['nvidia-smi'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        return r.returncode == 0
    except Exception:
        return False


def nvenc_available():
    try:
        p = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True, timeout=5)
        return 'h264_nvenc' in p.stdout
    except Exception:
        return False

GPU = gpu_available()
NVENC = GPU and nvenc_available()


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def render_video(src, dst, resolution, bitrate, preset, progress_cb, duration=None):
    width, height = resolution.split('x', 1)
    codec = 'h264_nvenc' if NVENC else 'libx264'
    actual_preset = preset
    if codec == 'h264_nvenc' and preset not in {'p1','p2','p3','p4','p5','p6','p7'}:
        actual_preset = 'p4'
    cmd = [
        'ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(src),
        '-vf',f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
        '-c:v',codec,'-preset',actual_preset,'-b:v',bitrate,'-c:a','aac','-movflags','+faststart',str(dst)
    ]
    # Ask FFmpeg for machine-readable progress on stdout.
    cmd = cmd[:-1] + ['-progress','pipe:1','-nostats',str(dst)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    while True:
        line = proc.stdout.readline()
        if line:
            line = line.strip()
            if line.startswith('out_time_ms='):
                # duration is discovered with ffprobe below when possible
                if duration:
                    pct = min(99.0, max(1.0, int(line.split('=',1)[1]) / 1_000_000 / duration * 100))
                    progress_cb(pct)
            elif line == 'progress=end':
                progress_cb(100.0)
        elif proc.poll() is not None:
            break
    stderr = proc.stderr.read()
    if proc.returncode != 0:
        raise RuntimeError(stderr[-1500:] or 'FFmpeg render failed')
    progress_cb(100.0)


def media_duration(path):
    try:
        p = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)], capture_output=True, text=True, timeout=5)
        return float(p.stdout.strip())
    except Exception:
        return None


def handle(conn, addr):
    job_dir = None
    try:
        conn.settimeout(60)
        send_json(conn, {**make_handshake('server'), 'gpu': GPU, 'nvenc': NVENC, 'server_time': time.time()})
        hello = recv_json(conn)
        if hello.get('type') != 'handshake' or hello.get('protocol') != 1:
            raise ValueError('Invalid client handshake')
        send_json(conn, {'type':'handshake_ack','status':'ready','latency_echo':time.time()})
        req = recv_json(conn)
        if req.get('type') != 'job':
            raise ValueError('Expected job request')
        job_id = req['job_id']
        job_dir = INBOX / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        src = job_dir / req['filename']
        log(f'Job {job_id}: receiving {req["filename"]} ({req["size"]} bytes)')
        send_json(conn, {'type':'file_ready','status':'send'})
        recv_file(conn, src, req['size'])
        if sha256_file(src) != req['sha256']:
            send_json(conn, {'type':'error','message':'Checksum mismatch after upload'})
            return
        send_json(conn, {'type':'transfer_verified','sha256':req['sha256']})
        out = OUTBOX / f'{job_id}_rendered.mp4'
        duration = media_duration(src)
        log(f'Job {job_id}: rendering with {"NVIDIA NVENC" if NVENC else "CPU fallback (libx264)"}')
        def progress(p):
            try: send_json(conn, {'type':'progress','percent':round(p,1),'stage':'rendering'})
            except OSError: pass
        # Set a simple duration-aware render through a wrapper environment; progress callback remains responsive.
        render_video(src, out, req.get('resolution','1280x720'), req.get('bitrate','2M'), req.get('preset','fast'), progress, duration)
        digest = sha256_file(out)
        send_json(conn, {'type':'render_complete','size':out.stat().st_size,'sha256':digest,'codec':'h264_nvenc' if NVENC else 'libx264'})
        send_json(conn, {'type':'output_ready','size':out.stat().st_size})
        send_file(conn, out)
        log(f'Job {job_id}: output sent successfully')
    except Exception as e:
        log(f'Client {addr} error: {e}')
        try: send_json(conn, {'type':'error','message':str(e)})
        except Exception: pass
    finally:
        try: conn.close()
        except Exception: pass


def serve(host=HOST, port=PORT):
    log(f'Remote GPU worker listening on {host}:{port}')
    log(f'GPU detected: {GPU}; NVENC encoder: {NVENC}')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port)); s.listen(8)
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    ap=argparse.ArgumentParser(description='Distributed Task Offloading Worker Daemon')
    ap.add_argument('--host',default=HOST); ap.add_argument('--port',type=int,default=PORT)
    args=ap.parse_args(); serve(args.host,args.port)
