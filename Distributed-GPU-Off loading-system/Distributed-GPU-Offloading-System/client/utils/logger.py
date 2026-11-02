# client/utils/logger.py
# Client-side file logger (separate from GUI log panel).

import logging
import sys
from pathlib import Path
from datetime import datetime


def get_logger(name: str) -> logging.Logger:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"client_{datetime.now().strftime('%Y%m%d')}.log"

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
