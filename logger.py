"""
logger.py
Centralized logging for ResearchMind AI.

Before this file, the only record of what happened was Streamlit's own
st.success/st.error messages — user-facing only, nothing saved to disk, and
nothing captured for errors that don't reach the UI at all (e.g. inside a
background LangGraph node). This module writes real, timestamped logs to
logs/app.log so issues can be traced after the fact.
"""

import logging
import os

from utils import ensure_dir

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

ensure_dir(LOG_DIR)

_logger = logging.getLogger("researchmind")
_logger.setLevel(logging.INFO)

if not _logger.handlers:  # avoid duplicate handlers on Streamlit re-runs
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)


def log_info(message: str):
    _logger.info(message)


def log_warning(message: str):
    _logger.warning(message)


def log_error(message: str, exc: Exception = None):
    if exc:
        _logger.error(f"{message} — {type(exc).__name__}: {exc}")
    else:
        _logger.error(message)


def log_action(action: str, detail: str = ""):
    """Log a user-triggered action (upload, analyze, export, agent call, etc.)
    in a consistent format, so the log file reads as an audit trail."""
    msg = f"ACTION: {action}"
    if detail:
        msg += f" | {detail}"
    _logger.info(msg)
