# client/utils/checksum.py
# SHA-256 checksum calculation for file integrity verification.

import hashlib
from pathlib import Path


def calculate_checksum(file_path: str, chunk_size: int = 65536) -> str:
    """Calculate SHA-256 checksum of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha.update(chunk)
    return sha.hexdigest()


def verify_checksum(file_path: str, expected: str) -> bool:
    """Return True if the file's checksum matches expected."""
    return calculate_checksum(file_path) == expected
