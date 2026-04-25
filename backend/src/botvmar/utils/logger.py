"""Structured logging with rotating file handler and colored console output."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from botvmar.config.env import LOG_LEVEL, LOGS_DIR

_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[35m",
}
_RESET = "\033[0m"


class ColoredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = _COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{_RESET}"
        return super().format(record)


_initialized = False


def _setup_root_logger() -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    root = logging.getLogger("bot")
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    fmt = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    file_handler = RotatingFileHandler(
        str(LOGS_DIR / "bot.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(ColoredFormatter(fmt, datefmt=datefmt))
    root.addHandler(console)


def get_logger(name: str) -> logging.Logger:
    _setup_root_logger()
    return logging.getLogger(f"bot.{name}")
