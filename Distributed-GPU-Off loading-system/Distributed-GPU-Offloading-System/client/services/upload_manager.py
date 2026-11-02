# client/services/upload_manager.py
# Handles the complete upload workflow: checksum → upload → validate.

from typing import Callable, Optional
from client.utils.checksum import calculate_checksum
from client.networking.api_client import APIClient
from client.utils.logger import get_logger

logger = get_logger("upload_manager")


def upload_with_verification(
    api: APIClient,
    file_path: str,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> tuple[bool, str, str]:
    """
    Full upload workflow:
      1. Calculate local checksum
      2. Upload file to server
      3. Verify server-side checksum

    Returns:
      (success, server_filename, error_message)
    """
    def log(msg: str):
        logger.info(msg)
        if log_callback:
            log_callback(msg)

    log("Calculating SHA-256 checksum...")
    try:
        checksum = calculate_checksum(file_path)
        log(f"Checksum: {checksum[:16]}...")
    except Exception as e:
        return False, "", f"Checksum calculation failed: {e}"

    log("Uploading video to remote worker...")
    try:
        result = api.upload_file(file_path, checksum, progress_callback)
    except Exception as e:
        return False, "", f"Upload failed: {e}"

    if not result.get("valid"):
        return False, "", f"Server rejected upload: {result.get('message', 'unknown error')}"

    server_filename = result.get("filename", "")
    log(f"Upload verified. Server file: {server_filename}")
    return True, server_filename, ""
