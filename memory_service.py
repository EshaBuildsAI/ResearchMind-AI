"""
memory_service.py
Smart Memory — persistent context that survives across sessions.

Unlike st.session_state (wiped on every refresh/restart), this writes to a
JSON file on disk per document, so the Research Agent can recall what was
already asked/answered about a document even after the app restarts.

This is intentionally simple (a JSON file, not a database) — it's honest
about being a lightweight persistence layer, not a production memory store.
"""

import json
import os

from constants import MEMORY_DIR
from utils import ensure_dir, safe_filename

MAX_MEMORY_ENTRIES_PER_DOC = 20  # keep memory files from growing unbounded


def _memory_path(doc_id: str) -> str:
    ensure_dir(MEMORY_DIR)
    filename = safe_filename(doc_id) + ".json"
    return os.path.join(MEMORY_DIR, filename)


def load_memory(doc_id: str) -> list:
    """Return the stored [{question, answer}, ...] history for a document.
    Returns an empty list if no memory file exists yet."""
    path = _memory_path(doc_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []  # corrupt or unreadable file — fail safe, don't crash the app


def save_memory_entry(doc_id: str, question: str, answer: str):
    """Append a Q&A pair to a document's persistent memory file,
    trimming to the most recent MAX_MEMORY_ENTRIES_PER_DOC entries."""
    history = load_memory(doc_id)
    history.append({"question": question, "answer": answer})
    history = history[-MAX_MEMORY_ENTRIES_PER_DOC:]

    path = _memory_path(doc_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except OSError:
        pass  # if disk write fails, memory just doesn't persist this turn — not fatal


def format_memory_for_prompt(doc_id: str, max_entries: int = 5) -> str:
    """Return the last few Q&A pairs as plain text, ready to prepend to a prompt
    so the agent has continuity across sessions. Empty string if no memory."""
    history = load_memory(doc_id)[-max_entries:]
    if not history:
        return ""

    lines = ["Earlier questions asked about this document (for context):"]
    for entry in history:
        lines.append(f"- Q: {entry['question']}\n  A: {entry['answer'][:200]}")
    return "\n".join(lines)


def clear_memory(doc_id: str):
    """Delete a document's memory file (used by 'Reset Workspace')."""
    path = _memory_path(doc_id)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
