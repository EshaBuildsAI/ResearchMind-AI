"""
utils.py
Shared helper functions used across the app (no business logic here).
"""

import os
import re
from datetime import datetime

from constants import SUPPORTED_FORMATS, MAX_FILE_SIZE_MB, CHUNK_SIZE, CHUNK_OVERLAP


def get_file_extension(filename: str) -> str:
    """Return lowercase file extension without the dot."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def is_supported_file(filename: str) -> bool:
    """Check whether the file extension is supported."""
    return get_file_extension(filename) in SUPPORTED_FORMATS


def is_file_size_valid(file_bytes: bytes) -> bool:
    """Check file size against MAX_FILE_SIZE_MB."""
    size_mb = len(file_bytes) / (1024 * 1024)
    return size_mb <= MAX_FILE_SIZE_MB


def clean_text(text: str) -> str:
    """Normalize whitespace and strip odd characters from extracted text."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\S\r\n]{2,}", " ", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Split text into overlapping chunks for embedding/retrieval."""
    text = clean_text(text)
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap

    return chunks


def format_timestamp() -> str:
    """Return a human-readable timestamp for logs/exports."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_filename(name: str) -> str:
    """Strip unsafe characters from a filename for saving to disk."""
    name = re.sub(r"[^\w\-_.]", "_", name)
    return name


def ensure_dir(path: str):
    """Create a directory if it doesn't already exist."""
    os.makedirs(path, exist_ok=True)


def truncate(text: str, max_chars: int = 300) -> str:
    """Truncate text for previews (e.g. recent documents list)."""
    return text if len(text) <= max_chars else text[:max_chars].rstrip() + "..."
