# ============================================================
# logger.py — FinSight Structured Logger
# Logs to both console and finsight.log file.
# Import get_logger() in any module that needs logging.
# ============================================================

import logging
import os
import sys
from datetime import datetime
from config import LOG_ENABLED, LOG_FILE, LOG_LEVEL


class ColorFormatter(logging.Formatter):
    """
    Adds color to console log output based on level.
    No color in file output.
    """
    COLORS = {
        "DEBUG":    "\033[36m",   # Cyan
        "INFO":     "\033[32m",   # Green
        "WARNING":  "\033[33m",   # Yellow
        "ERROR":    "\033[31m",   # Red
        "CRITICAL": "\033[41m",   # Red background
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname:<8}{self.RESET}"
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger with both console and file handlers.
    Call this at the top of any module:

        from logger import get_logger
        log = get_logger(__name__)

    Usage:
        log.info("Fetching data for RELIANCE.NS")
        log.warning("Balance sheet missing for ticker")
        log.error("Groq API call failed: timeout")
        log.debug("Beta calculated: 0.91")
    """
    logger = logging.getLogger(name)

    # Prevent duplicate handlers on re-import
    if logger.handlers:
        return logger

    if not LOG_ENABLED:
        logger.addHandler(logging.NullHandler())
        return logger

    # Map string level to logging constant
    level_map = {
        "DEBUG":   logging.DEBUG,
        "INFO":    logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR":   logging.ERROR,
    }
    level = level_map.get(LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    fmt_str  = "[%(asctime)s] %(levelname)s %(name)s — %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    # ── Console handler (with color) ──
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ColorFormatter(fmt_str, datefmt=date_fmt))
    logger.addHandler(console_handler)

    # ── File handler (plain text, no color) ──
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(fmt_str, datefmt=date_fmt))
        logger.addHandler(file_handler)
    except (PermissionError, OSError) as e:
        logger.warning(f"Could not create log file '{LOG_FILE}': {e}. Logging to console only.")

    return logger


def log_session_start():
    """Logs a session start marker — call once from run.py or app.py startup."""
    log = get_logger("session")
    log.info("=" * 55)
    log.info(f"FinSight session started — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 55)


def log_session_end():
    """Logs a session end marker."""
    log = get_logger("session")
    log.info("FinSight session ended.")
    log.info("=" * 55)
