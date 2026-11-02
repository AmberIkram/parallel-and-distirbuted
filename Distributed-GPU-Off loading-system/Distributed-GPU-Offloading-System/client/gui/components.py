# client/gui/components.py
# Reusable GUI widget components.

import customtkinter as ctk
from client.gui.theme import *


class SectionCard(ctk.CTkFrame):
    """Styled card container with optional title."""
    def __init__(self, parent, title: str = "", **kwargs):
        kwargs.setdefault("fg_color", BG_SECONDARY)
        kwargs.setdefault("corner_radius", 8)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", BORDER)
        super().__init__(parent, **kwargs)

        if title:
            self._title_label = ctk.CTkLabel(
                self, text=title, font=FONT_HEADING,
                text_color=ACCENT_BLUE, anchor="w"
            )
            self._title_label.pack(anchor="w", padx=14, pady=(10, 2))
            sep = ctk.CTkFrame(self, height=1, fg_color=BORDER)
            sep.pack(fill="x", padx=14, pady=(0, 8))


class StatusIndicator(ctk.CTkFrame):
    """A small colored dot with a text label."""
    def __init__(self, parent, label: str = "Disconnected", **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)

        self._dot = ctk.CTkLabel(self, text="●", font=("Segoe UI", 14),
                                 text_color=ACCENT_RED, width=20)
        self._dot.pack(side="left", padx=(0, 4))

        self._label = ctk.CTkLabel(self, text=label, font=FONT_STATUS,
                                   text_color=TEXT_SECONDARY)
        self._label.pack(side="left")

    def set_connected(self, text: str = "Connected"):
        self._dot.configure(text_color=ACCENT_GREEN)
        self._label.configure(text=text, text_color=ACCENT_GREEN)

    def set_disconnected(self, text: str = "Disconnected"):
        self._dot.configure(text_color=ACCENT_RED)
        self._label.configure(text=text, text_color=ACCENT_RED)

    def set_connecting(self, text: str = "Connecting..."):
        self._dot.configure(text_color=ACCENT_YELLOW)
        self._label.configure(text=text, text_color=ACCENT_YELLOW)


class LabeledValue(ctk.CTkFrame):
    """A label:value pair displayed horizontally."""
    def __init__(self, parent, label: str, value: str = "—", **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)

        ctk.CTkLabel(self, text=f"{label}:", font=FONT_LABEL,
                     text_color=TEXT_SECONDARY, width=130, anchor="w"
                     ).pack(side="left")

        self._value_label = ctk.CTkLabel(
            self, text=value, font=FONT_LABEL,
            text_color=TEXT_PRIMARY, anchor="w"
        )
        self._value_label.pack(side="left", fill="x", expand=True)

    def set_value(self, value: str):
        self._value_label.configure(text=value)

    def set_color(self, color: str):
        self._value_label.configure(text_color=color)


class LogPanel(ctk.CTkFrame):
    """Scrollable terminal-style log output panel."""
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("fg_color", BG_PRIMARY)
        kwargs.setdefault("corner_radius", 6)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", BORDER)
        super().__init__(parent, **kwargs)

        self._text = ctk.CTkTextbox(
            self,
            font=FONT_MONO,
            fg_color=BG_PRIMARY,
            text_color=TEXT_PRIMARY,
            wrap="word",
            state="disabled",
            scrollbar_button_color=BORDER,
        )
        self._text.pack(fill="both", expand=True, padx=2, pady=2)

        # Color tags
        self._text._textbox.tag_configure("info",    foreground=TEXT_PRIMARY)
        self._text._textbox.tag_configure("success", foreground=ACCENT_GREEN)
        self._text._textbox.tag_configure("warning", foreground=ACCENT_YELLOW)
        self._text._textbox.tag_configure("error",   foreground=ACCENT_RED)
        self._text._textbox.tag_configure("accent",  foreground=ACCENT_BLUE)
        self._text._textbox.tag_configure("progress",foreground=ACCENT_PURPLE)

    def log(self, message: str, level: str = "info"):
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"
        self._text.configure(state="normal")
        self._text._textbox.insert("end", line, level)
        self._text.configure(state="disabled")
        self._text._textbox.see("end")

    def clear(self):
        self._text.configure(state="normal")
        self._text.delete("0.0", "end")
        self._text.configure(state="disabled")

    def get_text(self) -> str:
        return self._text.get("0.0", "end")


class ProgressCard(ctk.CTkFrame):
    """Progress bar with percentage label and status message."""
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("fg_color", BG_SECONDARY)
        kwargs.setdefault("corner_radius", 8)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", BORDER)
        super().__init__(parent, **kwargs)

        self._pct_label = ctk.CTkLabel(
            self, text="0%", font=("Segoe UI", 22, "bold"),
            text_color=ACCENT_BLUE
        )
        self._pct_label.pack(pady=(12, 4))

        self._bar = ctk.CTkProgressBar(
            self, mode="determinate",
            fg_color=PROGRESS_BG, progress_color=PROGRESS_FG,
            height=12, corner_radius=6
        )
        self._bar.set(0)
        self._bar.pack(fill="x", padx=16, pady=(0, 6))

        self._status_label = ctk.CTkLabel(
            self, text="Idle", font=FONT_SMALL,
            text_color=TEXT_SECONDARY
        )
        self._status_label.pack(pady=(0, 10))

    def update_progress(self, pct: float, status_msg: str = ""):
        pct = max(0.0, min(100.0, pct))
        self._pct_label.configure(text=f"{pct:.0f}%")
        self._bar.set(pct / 100.0)
        if status_msg:
            self._status_label.configure(text=status_msg)

    def reset(self):
        self._pct_label.configure(text="0%")
        self._bar.set(0)
        self._status_label.configure(text="Idle")
