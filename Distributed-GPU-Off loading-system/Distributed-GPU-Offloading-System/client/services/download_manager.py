# client/services/download_manager.py
# Handles output file download and checksum verification.

from typing import Callable, Optional
from pathlib import Path
from client.utils.checksum import calculate_checksum, verify_checksum
from client.networking.api_client import APIClient
from client.services.file_manager import get_output_path
from client.utils.logger import get_logger

logger = get_logger("download_manager")


def download_with_verification(
    api: APIClient,
    job_id: str,
    output_format: str,
    expected_checksum: Optional[str] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> tuple[bool, str, str]:
    """
    Download the completed output file and verify its integrity.

    Returns:
      (success, local_output_path, error_message)
    """
    def log(msg: str):
        logger.info(msg)
        if log_callback:
            log_callback(msg)

    save_path = get_output_path(job_id, output_format)
    log(f"Downloading output to: {save_path}")

    try:
        api.download_output(job_id, save_path, progress_callback)
    except Exception as e:
        return False, "", f"Download failed: {e}"

    if not Path(save_path).exists():
        return False, "", "Downloaded file not found locally"

    size = Path(save_path).stat().st_size
    log(f"Downloaded {size / (1024*1024):.2f} MB")

    if expected_checksum:
        log("Verifying output file integrity...")
        if not verify_checksum(save_path, expected_checksum):
            local_cs = calculate_checksum(save_path)
            return False, save_path, (
                f"Output checksum mismatch!\n"
                f"Expected: {expected_checksum[:16]}...\n"
                f"Got:      {local_cs[:16]}..."
            )
        log("Output checksum verified successfully.")

    return True, save_path, ""
