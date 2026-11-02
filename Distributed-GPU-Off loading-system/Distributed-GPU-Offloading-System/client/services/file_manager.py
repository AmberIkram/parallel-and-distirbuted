# client/services/file_manager.py
# Handles local file selection, validation, and output management.

import os
from pathlib import Path
from shared.constants import ALLOWED_INPUT_EXTENSIONS


def get_file_info(file_path: str) -> dict:
    """Return basic info about a local file."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    size = p.stat().st_size
    return {
        "filename": p.name,
        "path": str(p.absolute()),
        "size_bytes": size,
        "size_mb": round(size / (1024 * 1024), 2),
        "extension": p.suffix.lower(),
        "format": p.suffix.lstrip(".").upper(),
    }


def validate_input_file(file_path: str) -> tuple[bool, str]:
    """Validate that the selected file is acceptable for upload."""
    p = Path(file_path)
    if not p.exists():
        return False, "File does not exist"
    if not p.is_file():
        return False, "Path is not a file"
    if p.suffix.lower() not in ALLOWED_INPUT_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_INPUT_EXTENSIONS))
        return False, f"Unsupported format. Allowed: {allowed}"
    if p.stat().st_size == 0:
        return False, "File is empty"
    return True, "OK"


def get_output_path(job_id: str, output_format: str) -> str:
    """Generate a local output file path in the outputs directory."""
    out_dir = Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    return str(out_dir / f"{job_id}_output.{output_format}")


def open_folder(path: str):
    """Open a folder in Windows Explorer."""
    import subprocess
    folder = Path(path)
    if folder.is_file():
        folder = folder.parent
    subprocess.Popen(["explorer", str(folder)])
