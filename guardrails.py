"""
guardrails.py
Basic safety checks for inputs and outputs. This is intentionally described
as "basic" and not "production-grade security" — it catches obvious cases
(empty input, oversized input, common prompt-injection phrasing, empty/junk
AI output) but does not do deep content moderation, PII detection, or
adversarial-input defense. That gap is documented honestly in roadmap.md.
"""

import re

from logger import log_warning

MAX_QUESTION_LENGTH = 2000
MIN_QUESTION_LENGTH = 2

# Common prompt-injection phrasings seen in documents or chat input.
# This is a pattern check, not a semantic one — it will miss cleverly
# reworded attempts, and can false-positive on legitimate text that happens
# to discuss prompt injection as a topic. It's a first line of defense only.
_INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) instructions",
    r"disregard (all )?(previous|prior|above) instructions",
    r"you are now (a|an) ",
    r"system prompt",
    r"act as (if )?you (have no|are not) restrictions",
    r"reveal your (instructions|system prompt|prompt)",
]
_INJECTION_REGEX = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def validate_question(question: str) -> tuple:
    """Validate a user-submitted question before sending it to the AI.
    Returns (is_valid: bool, cleaned_or_error: str)."""
    if not question or not question.strip():
        return False, "Question cannot be empty."

    question = question.strip()

    if len(question) < MIN_QUESTION_LENGTH:
        return False, "Question is too short."

    if len(question) > MAX_QUESTION_LENGTH:
        return False, f"Question is too long (max {MAX_QUESTION_LENGTH} characters)."

    return True, question


def check_for_injection_attempt(text: str) -> bool:
    """Flag text that matches common prompt-injection phrasing. Returns True
    if a pattern matched. This does NOT block the request automatically —
    callers decide what to do (e.g. warn, log, or still proceed with caution)."""
    if not text:
        return False
    matched = bool(_INJECTION_REGEX.search(text))
    if matched:
        log_warning(f"Possible prompt-injection pattern detected in input (first 100 chars): "
                    f"{text[:100]!r}")
    return matched


def validate_ai_output(output: str) -> tuple:
    """Sanity-check an AI response before showing it to the user.
    Returns (is_valid: bool, output_or_error: str)."""
    if not output or not output.strip():
        return False, "The AI returned an empty response. Please try again."

    if len(output.strip()) < 3:
        return False, "The AI response was too short to be useful. Please try again."

    return True, output.strip()
