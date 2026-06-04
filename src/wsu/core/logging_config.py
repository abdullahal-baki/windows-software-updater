"""Centralised logging configuration.

The application writes a rolling log to the per-user data directory so that
issues in a packaged build (where there is no console) can still be diagnosed.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

from wsu.core.paths import user_data_dir

_LOG_FILENAME = "updater.log"
_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure root logging once and return the application logger.

    Adds a rotating file handler (1 MB x 3 files) in the user data directory
    and, when a console is attached, a stream handler. Safe to call multiple
    times — configuration only happens on the first call.
    """
    global _CONFIGURED
    logger = logging.getLogger("wsu")
    if _CONFIGURED:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        log_path = os.path.join(user_data_dir(), _LOG_FILENAME)
        file_handler = RotatingFileHandler(
            log_path, maxBytes=1_048_576, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # If the log file cannot be opened, carry on without file logging.
        pass

    import sys

    if sys.stderr is not None:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logger.propagate = False
    _CONFIGURED = True
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a child logger under the ``wsu`` namespace."""
    if name:
        return logging.getLogger(f"wsu.{name}")
    return logging.getLogger("wsu")
