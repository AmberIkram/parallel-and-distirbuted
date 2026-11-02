# client/gui/dashboard.py
# Main application window — the complete GPU offloading dashboard.

import threading
import uuid
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox

from client.gui.theme import *
from client.gui.components import (
    SectionCard, StatusIndicator, LabeledValue, LogPanel, ProgressCard
)
from client.networking.api_client import APIClient
from client.networking.connection_manager import (
    load_connection_config, save_connection_config
)
from client.networking.websocket_client import ProgressWebSocketClient
from client.services.file_manager import (
    get_file_info, validate_input_file, get_output_path, open_folder
)
from client.services.upload_manager import upload_with_verification
from client.services.download_manager import download_with_verification
from shared.models import RenderConfig, JobSubmitRequest
from shared.constants import (
    RESOLUTIONS, PRESETS, BITRATES, OUTPUT_FORMATS,
    STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED,
    APP_NAME, APP_SUBTITLE
)


class Dashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._setup_window()
        self._init_state()
        self._build_ui()
        self._load_saved_config()

    # ── Window Setup ─────────────────────────────────────────────────────

    def _setup_window(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(APP_NAME)
        self.geometry("1280x820")
        self.minsize(1100, 720)
        self.configure(fg_color=BG_PRIMARY)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_state(self):
        self._api: Optional[APIClient] = None
        self._ws_client: Optional[ProgressWebSocketClient] = None
        self._connected = False
        self._current_job_id: Optional[str] = None
        self._current_file_path: Optional[str] = None
        self._server_gpu_info: dict = {}
        self._job_history: list[dict] = []
        self._rendering = False
        self._output_path: Optional[str] = None
        self._last_server_ip = ""
        self._last_server_port = 8000

    # ── UI Construction ───────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        content.columnconfigure(0, weight=1, minsize=300)
        content.columnconfigure(1, weight=2, minsize=500)
        content.rowconfigure(0, weight=1)

        self._build_left_panel(content)
        self._build_right_panel(content)

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=BG_SECONDARY,
                               corner_radius=0, height=64,
                               border_width=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=8)

        ctk.CTkLabel(
            title_frame, text="⚡ " + APP_NAME,
            font=FONT_TITLE, text_color=TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_frame, text=APP_SUBTITLE,
            font=FONT_SUBTITLE, text_color=TEXT_SECONDARY
        ).pack(anchor="w")

        # Status indicator in header
        self._header_status = StatusIndicator(header)
        self._header_status.pack(side="right", padx=20)

    # ── Left Panel ────────────────────────────────────────────────────────

    def _build_left_panel(self, parent):
        left = ctk.CTkFrame(parent, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=8)

        self._build_connection_panel(left)
        self._build_file_panel(left)
        self._build_config_panel(left)
        self._build_action_panel(left)

    def _build_connection_panel(self, parent):
        card = SectionCard(parent, title="Server Connection")
        card.pack(fill="x", pady=(0, 8))

        f = ctk.CTkFrame(card, fg_color="transparent")
        f.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(f, text="Server IP", font=FONT_LABEL,
                     text_color=TEXT_SECONDARY).grid(row=0, column=0, sticky="w")
        self._ip_entry = ctk.CTkEntry(
            f, placeholder_text="e.g. 192.168.1.1",
            fg_color=BG_TERTIARY, border_color=BORDER,
            text_color=TEXT_PRIMARY, font=FONT_LABEL, height=32
        )
        self._ip_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ctk.CTkLabel(f, text="Port", font=FONT_LABEL,
                     text_color=TEXT_SECONDARY).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self._port_entry = ctk.CTkEntry(
            f, placeholder_text="8000",
            fg_color=BG_TERTIARY, border_color=BORDER,
            text_color=TEXT_PRIMARY, font=FONT_LABEL, height=32
        )
        self._port_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
        f.columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="Auth Token", font=FONT_LABEL,
                     text_color=TEXT_SECONDARY).grid(row=2, column=0, sticky="w", pady=(6, 0))
        self._token_entry = ctk.CTkEntry(
            f, placeholder_text="Leave blank if none",
            fg_color=BG_TERTIARY, border_color=BORDER,
            text_color=TEXT_PRIMARY, font=FONT_LABEL, height=32, show="*"
        )
        self._token_entry.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 10))

        self._connect_btn = ctk.CTkButton(
            btn_row, text="Connect", command=self._connect,
            **BTN_PRIMARY, width=90
        )
        self._connect_btn.pack(side="left", padx=(0, 6))

        self._disconnect_btn = ctk.CTkButton(
            btn_row, text="Disconnect", command=self._disconnect,
            **BTN_SECONDARY, width=100, state="disabled"
        )
        self._disconnect_btn.pack(side="left", padx=(0, 6))

        self._test_btn = ctk.CTkButton(
            btn_row, text="Test", command=self._test_connection,
            **BTN_SECONDARY, width=70
        )
        self._test_btn.pack(side="left")

        # Connection info
        info_frame = ctk.CTkFrame(card, fg_color=BG_TERTIARY,
                                   corner_radius=6)
        info_frame.pack(fill="x", padx=14, pady=(0, 12))

        self._conn_status_ind = StatusIndicator(info_frame)
        self._conn_status_ind.pack(anchor="w", padx=10, pady=(8, 4))

        self._lv_latency   = LabeledValue(info_frame, "Latency")
        self._lv_latency.pack(fill="x", padx=10, pady=2)
        self._lv_gpu_name  = LabeledValue(info_frame, "Remote GPU")
        self._lv_gpu_name.pack(fill="x", padx=10, pady=2)
        self._lv_vram      = LabeledValue(info_frame, "VRAM")
        self._lv_vram.pack(fill="x", padx=10, pady=2)
        self._lv_exec_mode = LabeledValue(info_frame, "Exec Mode")
        self._lv_exec_mode.pack(fill="x", padx=10, pady=(2, 8))

    def _build_file_panel(self, parent):
        card = SectionCard(parent, title="Input File")
        card.pack(fill="x", pady=(0, 8))

        f = ctk.CTkFrame(card, fg_color="transparent")
        f.pack(fill="x", padx=14, pady=(0, 10))

        self._browse_btn = ctk.CTkButton(
            f, text="Browse Video File", command=self._browse_file,
            **BTN_SECONDARY
        )
        self._browse_btn.pack(fill="x", pady=(0, 8))

        info = ctk.CTkFrame(f, fg_color=BG_TERTIARY, corner_radius=6)
        info.pack(fill="x")

        self._lv_filename  = LabeledValue(info, "Filename")
        self._lv_filename.pack(fill="x", padx=10, pady=(6, 2))
        self._lv_filesize  = LabeledValue(info, "Size")
        self._lv_filesize.pack(fill="x", padx=10, pady=2)
        self._lv_fileformat= LabeledValue(info, "Format")
        self._lv_fileformat.pack(fill="x", padx=10, pady=(2, 6))

    def _build_config_panel(self, parent):
        card = SectionCard(parent, title="Rendering Configuration")
        card.pack(fill="x", pady=(0, 8))

        f = ctk.CTkFrame(card, fg_color="transparent")
        f.pack(fill="x", padx=14, pady=(0, 10))

        def row(label, row_idx):
            ctk.CTkLabel(f, text=label, font=FONT_LABEL,
                         text_color=TEXT_SECONDARY
                         ).grid(row=row_idx, column=0, sticky="w", pady=4)

        row("Resolution", 0)
        self._res_var = ctk.StringVar(value="Original")
        ctk.CTkOptionMenu(f, values=RESOLUTIONS, variable=self._res_var,
                          fg_color=BG_TERTIARY, button_color=BORDER,
                          button_hover_color=ACCENT_BLUE,
                          text_color=TEXT_PRIMARY, font=FONT_LABEL,
                          height=30
                          ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        row("Bitrate", 1)
        self._bitrate_var = ctk.StringVar(value="4M")
        ctk.CTkOptionMenu(f, values=BITRATES, variable=self._bitrate_var,
                          fg_color=BG_TERTIARY, button_color=BORDER,
                          button_hover_color=ACCENT_BLUE,
                          text_color=TEXT_PRIMARY, font=FONT_LABEL,
                          height=30
                          ).grid(row=1, column=1, sticky="ew", padx=(8, 0))

        row("Preset", 2)
        self._preset_var = ctk.StringVar(value="medium")
        ctk.CTkOptionMenu(f, values=PRESETS, variable=self._preset_var,
                          fg_color=BG_TERTIARY, button_color=BORDER,
                          button_hover_color=ACCENT_BLUE,
                          text_color=TEXT_PRIMARY, font=FONT_LABEL,
                          height=30
                          ).grid(row=2, column=1, sticky="ew", padx=(8, 0))

        row("Output Format", 3)
        self._fmt_var = ctk.StringVar(value="mp4")
        ctk.CTkOptionMenu(f, values=OUTPUT_FORMATS, variable=self._fmt_var,
                          fg_color=BG_TERTIARY, button_color=BORDER,
                          button_hover_color=ACCENT_BLUE,
                          text_color=TEXT_PRIMARY, font=FONT_LABEL,
                          height=30
                          ).grid(row=3, column=1, sticky="ew", padx=(8, 0))

        row("Execution Mode", 4)
        self._exec_var = ctk.StringVar(value="auto")
        ctk.CTkOptionMenu(f, values=["auto", "gpu", "cpu"],
                          variable=self._exec_var,
                          fg_color=BG_TERTIARY, button_color=BORDER,
                          button_hover_color=ACCENT_BLUE,
                          text_color=TEXT_PRIMARY, font=FONT_LABEL,
                          height=30
                          ).grid(row=4, column=1, sticky="ew", padx=(8, 0))

        f.columnconfigure(1, weight=1)

    def _build_action_panel(self, parent):
        card = ctk.CTkFrame(parent, fg_color="transparent")
        card.pack(fill="x", pady=(0, 8))

        self._start_btn = ctk.CTkButton(
            card, text="▶  START REMOTE RENDERING",
            command=self._start_rendering,
            **BTN_LARGE
        )
        self._start_btn.pack(fill="x", pady=(0, 6))

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x")

        self._cancel_btn = ctk.CTkButton(
            row2, text="✕  Cancel", command=self._cancel_rendering,
            **BTN_DANGER, width=110, state="disabled"
        )
        self._cancel_btn.pack(side="left", padx=(0, 6))

        self._open_folder_btn = ctk.CTkButton(
            row2, text="📁 Open Output Folder",
            command=self._open_output_folder,
            **BTN_SECONDARY
        )
        self._open_folder_btn.pack(side="left", padx=(0, 6))

        self._tensor_btn = ctk.CTkButton(
            row2, text="🔢 Tensor Test",
            command=self._run_tensor_test,
            **BTN_SECONDARY, width=110
        )
        self._tensor_btn.pack(side="left")

    # ── Right Panel ───────────────────────────────────────────────────────

    def _build_right_panel(self, parent):
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", pady=8)
        right.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(2, weight=0)
        right.columnconfigure(0, weight=1)

        self._build_stats_bar(right)
        self._build_log_panel(right)
        self._build_log_actions(right)

    def _build_stats_bar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        bar.columnconfigure((0, 1, 2, 3), weight=1)

        self._progress_card = ProgressCard(bar)
        self._progress_card.grid(row=0, column=0, columnspan=4, sticky="ew",
                                  padx=0, pady=(0, 8))

        # Stat tiles
        def tile(text, label, col):
            f = ctk.CTkFrame(bar, fg_color=BG_SECONDARY,
                              corner_radius=8, border_width=1,
                              border_color=BORDER)
            f.grid(row=1, column=col, sticky="ew",
                   padx=(0 if col == 0 else 6, 0))
            ctk.CTkLabel(f, text=text, font=("Segoe UI", 18, "bold"),
                         text_color=ACCENT_BLUE).pack(pady=(8, 0))
            lbl = ctk.CTkLabel(f, text=label, font=FONT_SMALL,
                                text_color=TEXT_SECONDARY)
            lbl.pack(pady=(0, 8))
            return lbl

        self._tile_jobs_done  = tile("0", "Jobs Done", 0)
        self._tile_job_status = tile("—", "Current Status", 1)
        self._tile_device     = tile("—", "Device", 2)
        self._tile_elapsed    = tile("—", "Elapsed", 3)

        # Store parent labels for value updates
        self._stat_jobs_done  = bar.winfo_children()[-4].winfo_children()[0]
        self._stat_job_status = bar.winfo_children()[-3].winfo_children()[0]
        self._stat_device     = bar.winfo_children()[-2].winfo_children()[0]
        self._stat_elapsed    = bar.winfo_children()[-1].winfo_children()[0]

    def _build_log_panel(self, parent):
        log_card = SectionCard(parent, title="Live Progress Terminal")
        log_card.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        self._log = LogPanel(log_card)
        self._log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _build_log_actions(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew")

        ctk.CTkButton(
            row, text="🗑 Clear Logs", command=self._log.clear,
            **BTN_SECONDARY, width=110
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            row, text="💾 Save Logs", command=self._save_logs,
            **BTN_SECONDARY, width=110
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            row, text="📊 Job History", command=self._show_history,
            **BTN_SECONDARY, width=110
        ).pack(side="left")

    # ── Logic: Connection ─────────────────────────────────────────────────

    def _load_saved_config(self):
        cfg = load_connection_config()
        if cfg.get("server_ip"):
            self._ip_entry.insert(0, cfg["server_ip"])
        self._port_entry.insert(0, str(cfg.get("server_port", 8000)))
        if cfg.get("auth_token") and cfg["auth_token"] != "changeme-secret-token":
            self._token_entry.insert(0, cfg["auth_token"])

    def _connect(self):
        ip = self._ip_entry.get().strip()
        port_str = self._port_entry.get().strip()
        token = self._token_entry.get().strip()

        if not ip:
            self._log.log("Please enter the server IP address.", "error")
            return
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError()
        except ValueError:
            self._log.log("Invalid port number.", "error")
            return

        self._conn_status_ind.set_connecting()
        self._header_status.set_connecting()
        self._connect_btn.configure(state="disabled")
        self._log.log(f"Connecting to {ip}:{port}...", "info")

        threading.Thread(
            target=self._do_connect, args=(ip, port, token), daemon=True
        ).start()

    def _do_connect(self, ip: str, port: int, token: str):
        try:
            api = APIClient(ip, port, token)

            # HELLO / SERVER_READY handshake
            self._log_safe("Sending HELLO handshake...")
            hs = api.handshake()
            self._log_safe(f"SERVER_READY — {hs.server_name} v{hs.server_version}", "success")

            # PING / PONG latency
            self._log_safe("Measuring network latency...")
            _, rtt = api.ping()
            self._log_safe(f"Latency: {rtt:.1f} ms", "success")

            # GPU info
            gpu = hs.gpu_info
            self._server_gpu_info = gpu

            self._api = api
            self._connected = True
            self._last_server_ip = ip
            self._last_server_port = port

            save_connection_config(ip, port, token)

            self.after(0, lambda: self._on_connect_success(ip, port, rtt, gpu))

        except Exception as e:
            msg = self._friendly_error(e)
            self.after(0, lambda: self._on_connect_fail(msg))

    def _on_connect_success(self, ip, port, rtt, gpu):
        self._conn_status_ind.set_connected(f"Connected to {ip}:{port}")
        self._header_status.set_connected(f"Connected | {rtt:.0f}ms")
        self._connect_btn.configure(state="disabled")
        self._disconnect_btn.configure(state="normal")

        self._lv_latency.set_value(f"{rtt:.1f} ms")
        self._lv_latency.set_color(ACCENT_GREEN if rtt < 100 else ACCENT_YELLOW)

        gpu_name = gpu.get("gpu_name") or "Not available"
        vram = gpu.get("vram_mb")
        exec_mode = gpu.get("execution_mode", "CPU")

        self._lv_gpu_name.set_value(gpu_name)
        self._lv_vram.set_value(f"{vram} MB" if vram else "N/A")
        self._lv_exec_mode.set_value(exec_mode)
        self._lv_exec_mode.set_color(
            ACCENT_GREEN if exec_mode == "NVENC" else
            ACCENT_YELLOW if exec_mode == "CUDA" else TEXT_SECONDARY
        )

        self._log.log(f"Connected to {ip}:{port}", "success")
        if gpu.get("available"):
            self._log.log(f"Remote GPU: {gpu_name} ({vram} MB VRAM)", "success")
        else:
            self._log.log("No NVIDIA GPU on remote — using CPU rendering", "warning")
        self._log.log(f"Execution mode: {exec_mode}", "accent")

    def _on_connect_fail(self, msg):
        self._conn_status_ind.set_disconnected("Connection failed")
        self._header_status.set_disconnected()
        self._connect_btn.configure(state="normal")
        self._log.log(f"Connection failed: {msg}", "error")

    def _disconnect(self):
        if self._api:
            self._api.close()
            self._api = None
        self._connected = False
        self._conn_status_ind.set_disconnected()
        self._header_status.set_disconnected()
        self._connect_btn.configure(state="normal")
        self._disconnect_btn.configure(state="disabled")
        self._lv_latency.set_value("—")
        self._lv_gpu_name.set_value("—")
        self._lv_vram.set_value("—")
        self._lv_exec_mode.set_value("—")
        self._log.log("Disconnected from server.", "warning")

    def _test_connection(self):
        if not self._connected or not self._api:
            self._log.log("Not connected. Please connect first.", "error")
            return
        threading.Thread(target=self._do_test, daemon=True).start()

    def _do_test(self):
        try:
            _, rtt = self._api.ping()
            self.after(0, lambda: self._log.log(
                f"Ping OK — RTT: {rtt:.1f} ms", "success"))
            self.after(0, lambda: self._lv_latency.set_value(f"{rtt:.1f} ms"))
        except Exception as e:
            self.after(0, lambda: self._log.log(
                f"Ping failed: {e}", "error"))

    # ── Logic: File Selection ─────────────────────────────────────────────

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video Files", "*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv *.m4v"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return

        valid, msg = validate_input_file(path)
        if not valid:
            self._log.log(f"Invalid file: {msg}", "error")
            return

        info = get_file_info(path)
        self._current_file_path = path
        self._lv_filename.set_value(info["filename"])
        self._lv_filesize.set_value(f"{info['size_mb']} MB")
        self._lv_fileformat.set_value(info["format"])
        self._log.log(f"Selected: {info['filename']} ({info['size_mb']} MB)", "info")

    # ── Logic: Rendering ──────────────────────────────────────────────────

    def _start_rendering(self):
        if not self._connected:
            self._log.log("Not connected to server.", "error")
            return
        if not self._current_file_path:
            self._log.log("No video file selected.", "error")
            return
        if self._rendering:
            self._log.log("A render job is already in progress.", "warning")
            return

        config = RenderConfig(
            resolution=self._res_var.get(),
            bitrate=self._bitrate_var.get(),
            preset=self._preset_var.get(),
            output_format=self._fmt_var.get(),
            execution_mode=self._exec_var.get(),
        )
        job_id = str(uuid.uuid4())
        self._current_job_id = job_id
        self._rendering = True
        self._output_path = None

        self._start_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._progress_card.reset()
        self._update_stat("stat_job_status", "Uploading")

        threading.Thread(
            target=self._run_render_workflow,
            args=(job_id, self._current_file_path, config),
            daemon=True,
        ).start()

    def _run_render_workflow(self, job_id: str, file_path: str, config: RenderConfig):
        api = self._api
        start_time = time.time()

        def log(msg, level="info"):
            self.after(0, lambda m=msg, l=level: self._log.log(m, l))

        def progress(pct, msg=""):
            self.after(0, lambda p=pct, m=msg: self._progress_card.update_progress(p, m))

        def set_status(s):
            self.after(0, lambda: self._update_stat("stat_job_status", s))

        try:
            # ── Upload ──────────────────────────────────────
            log("Starting upload workflow...")

            def upload_progress(sent, total):
                pct = (sent / total * 40) if total else 0
                progress(pct, f"Uploading... {sent//(1024*1024)}/{total//(1024*1024)} MB")

            ok, server_filename, err = upload_with_verification(
                api, file_path,
                log_callback=log,
                progress_callback=upload_progress,
            )
            if not ok:
                raise RuntimeError(f"Upload failed: {err}")

            log(f"Upload complete. Server file: {server_filename}", "success")
            set_status("Submitting")
            progress(42, "Upload complete. Submitting job...")

            # ── Submit Job ───────────────────────────────────
            from client.utils.checksum import calculate_checksum
            file_info = get_file_info(file_path)
            checksum = calculate_checksum(file_path)

            req = JobSubmitRequest(
                job_id=job_id,
                input_filename=server_filename,
                file_size=file_info["size_bytes"],
                input_checksum=checksum,
                render_config=config,
            )
            job = api.submit_job(req)
            log(f"Job submitted: {job_id[:8]}...", "success")
            set_status("Processing")
            progress(45, "Job queued. Waiting for remote execution...")

            # ── WebSocket Progress Stream ────────────────────
            ws_done = threading.Event()
            render_failed = [False]
            render_error = [""]

            def on_progress(data: dict):
                pct = data.get("progress", 0)
                msg = data.get("message", "")
                device = data.get("execution_device", "CPU")
                # Map 0-100% render progress to 45-90% overall
                overall = 45 + (pct * 0.45)
                self.after(0, lambda p=overall, m=msg: self._progress_card.update_progress(p, m))
                self.after(0, lambda d=device: self._update_stat("stat_device", d))
                elapsed = time.time() - start_time
                self.after(0, lambda e=elapsed: self._update_stat(
                    "stat_elapsed", f"{e:.0f}s"))

            def on_complete(data: dict):
                ws_done.set()

            def on_ws_error(msg: str):
                render_error[0] = msg
                render_failed[0] = True
                ws_done.set()

            ws = ProgressWebSocketClient(
                self._last_server_ip, self._last_server_port,
                job_id, on_progress, on_ws_error, on_complete
            )
            ws.start()
            self._ws_client = ws

            # Poll job status as fallback in case WS misses the completion
            max_wait = 3600  # 1 hour max
            waited = 0
            poll_interval = 3
            while not ws_done.is_set() and waited < max_wait:
                ws_done.wait(timeout=poll_interval)
                waited += poll_interval
                if ws_done.is_set():
                    break
                # Poll HTTP fallback
                try:
                    status = api.get_job_status(job_id)
                    if status.status in (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED):
                        ws_done.set()
                        break
                except Exception:
                    pass

            ws.stop()

            if render_failed[0]:
                raise RuntimeError(render_error[0])

            # Check final job status
            final = api.get_job_status(job_id)
            if final.status == STATUS_CANCELLED:
                raise RuntimeError("Job was cancelled")
            if final.status == STATUS_FAILED:
                raise RuntimeError(f"Rendering failed: {final.error_message}")

            log("Remote rendering complete.", "success")
            progress(92, "Downloading output...")
            set_status("Downloading")

            # ── Download ─────────────────────────────────────
            def dl_progress(recv, total):
                pct = 92 + (recv / total * 7) if total else 92
                progress(pct, f"Downloading {recv//(1024*1024)}/{total//(1024*1024)} MB...")

            ok, out_path, err = download_with_verification(
                api, job_id,
                output_format=config.output_format,
                expected_checksum=final.output_checksum,
                log_callback=log,
                progress_callback=dl_progress,
            )
            if not ok:
                raise RuntimeError(f"Download failed: {err}")

            self._output_path = out_path
            elapsed = time.time() - start_time
            log(f"✓ Output saved to: {out_path}", "success")
            log(f"✓ Total time: {elapsed:.1f}s | Device: {final.execution_device}", "success")
            progress(100, f"Complete! {elapsed:.1f}s | {final.execution_device}")

            # Add to history
            self._job_history.append({
                "job_id": job_id,
                "file": Path(file_path).name,
                "device": final.execution_device,
                "duration": f"{elapsed:.1f}s",
                "output": out_path,
                "status": "Completed",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            })

            jobs_done = len([j for j in self._job_history if j["status"] == "Completed"])
            self.after(0, lambda: self._update_stat("stat_jobs_done", str(jobs_done)))
            set_status("Completed")

        except Exception as e:
            log(f"Error: {e}", "error")
            set_status("Failed")
            progress(0, "Failed")

        finally:
            self._rendering = False
            self.after(0, lambda: self._start_btn.configure(state="normal"))
            self.after(0, lambda: self._cancel_btn.configure(state="disabled"))

    def _cancel_rendering(self):
        if not self._current_job_id or not self._api:
            return
        job_id = self._current_job_id
        if self._ws_client:
            self._ws_client.stop()
        try:
            self._api.cancel_job(job_id)
            self._log.log(f"Cancellation requested for job {job_id[:8]}...", "warning")
        except Exception as e:
            self._log.log(f"Cancel error: {e}", "error")

    # ── Tensor Test ───────────────────────────────────────────────────────

    def _run_tensor_test(self):
        if not self._connected or not self._api:
            self._log.log("Not connected to server.", "error")
            return
        from shared.models import TensorJobRequest
        req = TensorJobRequest(rows_a=1024, cols_a=1024, cols_b=1024, execution_mode="auto")
        self._log.log("Submitting tensor computation (1024x1024 matrix multiply)...", "accent")
        threading.Thread(target=self._do_tensor, args=(req,), daemon=True).start()

    def _do_tensor(self, req):
        try:
            result = self._api.tensor_compute(req)
            self.after(0, lambda: self._log.log(
                f"Tensor result — Device: {result.execution_device} | "
                f"Time: {result.computation_time_ms:.2f}ms | "
                f"Shape: {result.matrix_shape}", "success"
            ))
        except Exception as e:
            self.after(0, lambda: self._log.log(f"Tensor test failed: {e}", "error"))

    # ── Utilities ─────────────────────────────────────────────────────────

    def _log_safe(self, msg: str, level: str = "info"):
        self.after(0, lambda m=msg, l=level: self._log.log(m, l))

    def _update_stat(self, attr: str, value: str):
        """Update a stat tile value label."""
        mapping = {
            "stat_jobs_done": self._stat_jobs_done,
            "stat_job_status": self._stat_job_status,
            "stat_device": self._stat_device,
            "stat_elapsed": self._stat_elapsed,
        }
        lbl = mapping.get(attr)
        if lbl:
            lbl.configure(text=value)

    def _open_output_folder(self):
        path = self._output_path or "outputs"
        try:
            open_folder(path)
        except Exception as e:
            self._log.log(f"Cannot open folder: {e}", "error")

    def _save_logs(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfile=f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._log.get_text())
            self._log.log(f"Logs saved to {path}", "success")

    def _show_history(self):
        win = ctk.CTkToplevel(self)
        win.title("Job History")
        win.geometry("700x400")
        win.configure(fg_color=BG_PRIMARY)

        ctk.CTkLabel(win, text="Job History", font=FONT_HEADING,
                     text_color=ACCENT_BLUE).pack(pady=10)

        text = ctk.CTkTextbox(win, fg_color=BG_SECONDARY,
                               text_color=TEXT_PRIMARY, font=FONT_MONO)
        text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        if not self._job_history:
            text.insert("end", "No jobs yet.\n")
        else:
            for j in reversed(self._job_history):
                text.insert("end",
                    f"[{j['timestamp']}] {j['file']} → {j['status']} "
                    f"({j['device']}, {j['duration']})\n"
                )
        text.configure(state="disabled")

    def _friendly_error(self, e: Exception) -> str:
        msg = str(e)
        if "Connection refused" in msg or "ConnectError" in msg:
            return "Connection refused — is the server running?"
        if "timed out" in msg.lower() or "timeout" in msg.lower():
            return "Connection timed out — check the IP address and firewall"
        if "Name or service not known" in msg or "getaddrinfo" in msg:
            return "Invalid server IP address"
        if "protocol" in msg.lower():
            return f"Protocol error: {msg}"
        return msg

    def _on_close(self):
        if self._ws_client:
            self._ws_client.stop()
        if self._api:
            self._api.close()
        self.destroy()
