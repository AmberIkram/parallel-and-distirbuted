# server/utils/logger.py
# Centralized logging for the server

import logging
import sys
from pathlib import Path
from datetime import datetime
from server.utils.config import CONFIG


def get_logger(name: str) -> logging.Logger:
    log_dir = Path(CONFIG.get("log_dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"server_{datetime.now().strftime('%Y%m%d')}.log"

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = getattr(logging, CONFIG.get("log_level", "INFO").upper(), logging.INFO)
    logger.setLevel(level)

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
