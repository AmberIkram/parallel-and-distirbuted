# server/services/file_validator.py
# Validates uploaded files: extension, size, checksum, path traversal prevention.

import hashlib
import os
from pathlib import Path
from shared.constants import ALLOWED_INPUT_EXTENSIONS
from server.utils.config import CONFIG
from server.utils.logger import get_logger

logger = get_logger("file_validator")


def safe_filename(filename: str) -> str:
    """
    Strip path components and dangerous characters.
    Prevents path traversal attacks.
    """
    # Take only the final component
    name = Path(filename).name
    # Replace any remaining separators
    name = name.replace("/", "_").replace("\\", "_").replace("..", "_")
    # Allow only alphanumeric, dash, underscore, dot
    safe = "".join(c for c in name if c.isalnum() or c in "-_.")
    return safe or "unnamed_file"


def validate_extension(filename: str) -> tuple[bool, str]:
    """Check that the file extension is in the allowed set."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_INPUT_EXTENSIONS:
        return False, f"File extension '{ext}' is not allowed. Allowed: {ALLOWED_INPUT_EXTENSIONS}"
    return True, "OK"


def validate_file_size(file_path: str) -> tuple[bool, str]:
    """Check file does not exceed the configured size limit."""
    max_bytes = int(CONFIG.get("max_upload_size_mb", 2048)) * 1024 * 1024
    size = os.path.getsize(file_path)
    if size > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        return False, f"File size {size // (1024*1024)} MB exceeds limit of {limit_mb} MB"
    if size == 0:
        return False, "File is empty"
    return True, "OK"


def calculate_checksum(file_path: str) -> str:
    """Calculate SHA-256 checksum of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def verify_checksum(file_path: str, expected: str) -> tuple[bool, str]:
    """Verify that a file's checksum matches the expected value."""
    actual = calculate_checksum(file_path)
    if actual != expected:
        return False, f"Checksum mismatch: expected {expected}, got {actual}"
    return True, "Checksum verified"


def validate_uploaded_file(file_path: str, expected_checksum: str, original_filename: str) -> tuple[bool, str]:
    """Full validation pipeline for an uploaded file."""
    valid_ext, msg = validate_extension(original_filename)
    if not valid_ext:
        return False, msg

    if not Path(file_path).exists():
        return False, "File does not exist on server"

    valid_size, msg = validate_file_size(file_path)
    if not valid_size:
        return False, msg

    valid_cs, msg = verify_checksum(file_path, expected_checksum)
    if not valid_cs:
        return False, msg

    return True, "File validation passed"
