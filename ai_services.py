"""
ai_services.py
All AI logic lives here. Wraps the OpenAI API (gpt-4o-mini) and uses prompts.py
for prompt construction. No UI code and no file-parsing code in this module.
"""

import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from constants import OPENAI_MODEL, OPENAI_API_KEY_ENV
from prompts import (
    summary_prompt,
    chat_prompt,
    quiz_prompt,
    flashcard_prompt,
    research_gap_prompt,
    presentation_prompt,
    literature_review_prompt,
    proposal_prompt,
)

_client = None

# Load variables from a .env file (if present) into the environment.
# This must happen before _get_client() reads OPENAI_API_KEY.
load_dotenv()


def _get_client() -> OpenAI:
    """Build the OpenAI client once. Checks environment/.env first (local dev),
    then Streamlit secrets (Streamlit Cloud deployment)."""
    global _client
    if _client is None:
        api_key = os.environ.get(OPENAI_API_KEY_ENV)

        if not api_key:
            try:
                import streamlit as st
                api_key = st.secrets.get(OPENAI_API_KEY_ENV)
            except Exception:
                pass

        if not api_key:
            raise EnvironmentError(
                f"{OPENAI_API_KEY_ENV} not set. Locally, add it to a .env file. "
                f"On Streamlit Cloud, add it under App settings → Secrets."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def _generate(prompt: str) -> str:
    """Send a prompt to GPT-4o-mini and return the plain text response."""
    client = _get_client()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()


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


def extract_topic(text: str) -> str:
    """Extract a short (3-6 word) search-friendly topic from a document.
    Used to feed Recommendation/Timeline/Innovation agents a query for
    external paper search, instead of sending the whole document as a query."""
    prompt = (
        "In 3 to 6 words, state the core research topic of the document below. "
        "Return ONLY the topic phrase, nothing else.\n\nDOCUMENT:\n"
        f"{text[:2000]}\n\nTOPIC:"
    )
    topic = _generate(prompt)
    return topic.strip().strip('"')


def generate_proposal(text: str, degree_level: str = "BS", university: str = "") -> str:
    return _generate(proposal_prompt(text, degree_level, university))


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
