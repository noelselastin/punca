"""Every run writes to logs/punca.log (rotating) as well as stderr. Read this file first when something fails."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

import config


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("punca")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(config.LOG_DIR / "punca.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as exc:  # read-only checkout etc.
        print(f"punca: could not open log file: {exc}", file=sys.stderr)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    logger.propagate = False
    return logger
