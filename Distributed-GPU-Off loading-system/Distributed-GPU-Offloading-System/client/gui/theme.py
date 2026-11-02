# client/gui/theme.py
# Color palette and font definitions for the dark GPU dashboard theme.

# ── Colors ───────────────────────────────────────────────────────────────────
BG_PRIMARY    = "#0d1117"   # Deep charcoal background
BG_SECONDARY  = "#161b22"   # Card/panel background
BG_TERTIARY   = "#21262d"   # Input fields, inner panels
BORDER        = "#30363d"   # Subtle borders
ACCENT_BLUE   = "#58a6ff"   # Primary accent
ACCENT_PURPLE = "#bc8cff"   # Secondary accent
ACCENT_GREEN  = "#3fb950"   # Success / connected
ACCENT_YELLOW = "#d29922"   # Warning
ACCENT_RED    = "#f85149"   # Error / disconnected
TEXT_PRIMARY  = "#e6edf3"   # Main text
TEXT_SECONDARY= "#8b949e"   # Dimmed text
TEXT_MUTED    = "#484f58"   # Very dimmed
PROGRESS_BG   = "#21262d"
PROGRESS_FG   = "#58a6ff"

# ── Fonts ────────────────────────────────────────────────────────────────────
FONT_TITLE    = ("Segoe UI", 20, "bold")
FONT_SUBTITLE = ("Segoe UI", 11)
FONT_HEADING  = ("Segoe UI", 13, "bold")
FONT_LABEL    = ("Segoe UI", 10)
FONT_SMALL    = ("Segoe UI", 9)
FONT_MONO     = ("Consolas", 9)
FONT_BUTTON   = ("Segoe UI", 10, "bold")
FONT_STATUS   = ("Segoe UI", 10)

# ── CustomTkinter appearance configuration ───────────────────────────────────
CTK_DEFAULTS = {
    "appearance_mode": "dark",
    "color_theme": "blue",
}

# Button styles
BTN_PRIMARY = {
    "fg_color": ACCENT_BLUE,
    "hover_color": "#388bfd",
    "text_color": "#ffffff",
    "corner_radius": 6,
    "font": FONT_BUTTON,
    "height": 36,
}
BTN_SECONDARY = {
    "fg_color": BG_TERTIARY,
    "hover_color": "#2d333b",
    "text_color": TEXT_PRIMARY,
    "border_color": BORDER,
    "border_width": 1,
    "corner_radius": 6,
    "font": FONT_BUTTON,
    "height": 36,
}
BTN_DANGER = {
    "fg_color": "#6e2020",
    "hover_color": ACCENT_RED,
    "text_color": "#ffffff",
    "corner_radius": 6,
    "font": FONT_BUTTON,
    "height": 36,
}
BTN_SUCCESS = {
    "fg_color": "#1a4028",
    "hover_color": ACCENT_GREEN,
    "text_color": "#ffffff",
    "corner_radius": 6,
    "font": FONT_BUTTON,
    "height": 36,
}
BTN_LARGE = {
    "fg_color": ACCENT_BLUE,
    "hover_color": "#388bfd",
    "text_color": "#ffffff",
    "corner_radius": 8,
    "font": ("Segoe UI", 13, "bold"),
    "height": 48,
}
