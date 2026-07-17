"""
ai_services.py
All AI logic lives here. Wraps the Google Gemini API and uses prompts.py
for prompt construction. No UI code and no file-parsing code in this module.
"""

import os
import re

from dotenv import load_dotenv
import google.generativeai as genai

from constants import GEMINI_MODEL, GEMINI_API_KEY_ENV
from prompts import (
    summary_prompt,
    chat_prompt,
    quiz_prompt,
    flashcard_prompt,
    research_gap_prompt,
    presentation_prompt,
    literature_review_prompt,
)

_configured = False

# Load variables from a .env file (if present) into the environment.
# This must happen before _configure() reads GEMINI_API_KEY.
load_dotenv()


def _configure():
    """Configure the Gemini client once, using the API key from environment variables."""
    global _configured
    if not _configured:
        api_key = os.environ.get(GEMINI_API_KEY_ENV)
        if not api_key:
            raise EnvironmentError(
                f"{GEMINI_API_KEY_ENV} not set. Add it to your environment "
                f"or .streamlit/secrets.toml before using AI features."
            )
        genai.configure(api_key=api_key)
        _configured = True


def _generate(prompt: str) -> str:
    """Send a prompt to Gemini and return the plain text response."""
    _configure()
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)
    return response.text.strip()


def generate_summary(text: str, length: str = "medium") -> str:
    return _generate(summary_prompt(text, length))


def answer_question(question: str, context_chunks: list) -> str:
    if not context_chunks:
        return "I couldn't find relevant content in this document to answer that."
    return _generate(chat_prompt(question, context_chunks))


def generate_quiz(text: str, num_questions: int = 5) -> list:
    """Returns a list of dicts: {question, options: {A,B,C,D}, correct}."""
    raw = _generate(quiz_prompt(text, num_questions))
    return _parse_quiz(raw)


def generate_flashcards(text: str, num_cards: int = 10) -> list:
    """Returns a list of dicts: {front, back}."""
    raw = _generate(flashcard_prompt(text, num_cards))
    return _parse_flashcards(raw)


def generate_literature_review(text: str) -> str:
    return _generate(literature_review_prompt(text))


def detect_research_gaps(text: str) -> str:
    return _generate(research_gap_prompt(text))


def generate_presentation_outline(text: str, num_slides: int = 8) -> list:
    """Returns a list of dicts: {title, bullets: [...]}."""
    raw = _generate(presentation_prompt(text, num_slides))
    return _parse_presentation(raw)


# ---------------- PARSERS (raw model text -> structured data) ----------------

def _parse_quiz(raw: str) -> list:
    questions = []
    blocks = re.split(r"\n(?=Q\d+:)", raw.strip())

    for block in blocks:
        q_match = re.search(r"Q\d+:\s*(.+)", block)
        options = dict(re.findall(r"([A-D])\)\s*(.+)", block))
        correct_match = re.search(r"Correct:\s*([A-D])", block)

        if q_match and options and correct_match:
            questions.append({
                "question": q_match.group(1).strip(),
                "options": options,
                "correct": correct_match.group(1).strip(),
            })

    return questions


def _parse_flashcards(raw: str) -> list:
    cards = []
    blocks = re.split(r"\n(?=Front:)", raw.strip())

    for block in blocks:
        front_match = re.search(r"Front:\s*(.+)", block)
        back_match = re.search(r"Back:\s*(.+)", block)

        if front_match and back_match:
            cards.append({
                "front": front_match.group(1).strip(),
                "back": back_match.group(1).strip(),
            })

    return cards


def _parse_presentation(raw: str) -> list:
    slides = []
    blocks = re.split(r"\n(?=Slide\s*\d+:)", raw.strip())

    for block in blocks:
        title_match = re.search(r"Slide\s*\d+:\s*(.+)", block)
        bullets = re.findall(r"-\s*(.+)", block)

        if title_match:
            slides.append({
                "title": title_match.group(1).strip(),
                "bullets": [b.strip() for b in bullets],
            })

    return slides
