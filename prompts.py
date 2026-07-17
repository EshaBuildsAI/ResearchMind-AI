"""
prompts.py
Centralized prompt templates for all AI operations.
Keeping prompts here (not scattered in ai_services.py) makes them easy to tune.
"""


def summary_prompt(text: str, length: str = "medium") -> str:
    length_map = {
        "short": "in 3-4 concise bullet points",
        "medium": "in 6-8 bullet points covering key findings, methods, and conclusions",
        "detailed": "as a detailed structured summary with sections: Overview, Methodology, "
                    "Key Findings, and Conclusion",
    }
    instruction = length_map.get(length, length_map["medium"])

    return f"""You are a research assistant. Summarize the following document {instruction}.
Be accurate and only use information present in the text. Do not invent facts.

DOCUMENT:
{text}

SUMMARY:"""


def chat_prompt(question: str, context_chunks: list) -> str:
    context = "\n\n".join(f"[Excerpt {i+1}]\n{chunk}" for i, chunk in enumerate(context_chunks))

    return f"""You are ResearchMind AI, a research assistant. Answer the user's question
using ONLY the context excerpts below. If the answer isn't in the context, say so honestly
instead of guessing.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:"""


def quiz_prompt(text: str, num_questions: int = 5) -> str:
    return f"""Create {num_questions} multiple-choice quiz questions based on the document below.
For each question, provide 4 options (A-D) and clearly mark the correct answer.
Return the result in this exact format for each question:

Q1: <question text>
A) <option>
B) <option>
C) <option>
D) <option>
Correct: <letter>

DOCUMENT:
{text}

QUIZ:"""


def flashcard_prompt(text: str, num_cards: int = 10) -> str:
    return f"""Create {num_cards} flashcards from the document below.
Each flashcard should test one key concept, term, or fact.
Return the result in this exact format for each card:

Front: <term or question>
Back: <definition or answer>

DOCUMENT:
{text}

FLASHCARDS:"""


def literature_review_prompt(text: str) -> str:
    return f"""You are a research assistant writing a literature review section based on the
document below. Structure your response under these headings:

1. Introduction — what field/topic this work belongs to
2. Related Work — key themes, methods, and prior work discussed or referenced
3. Critical Analysis — strengths and weaknesses of the approach
4. Conclusion — how this document fits into the broader research landscape

Only use information present in the document. Do not invent citations.

DOCUMENT:
{text}

LITERATURE REVIEW:"""


def research_gap_prompt(text: str) -> str:
    return f"""You are a research analyst. Carefully review the document below and identify:
1. Missing topics or areas not addressed
2. Explicitly stated future work
3. Dataset or sample limitations
4. Methodology gaps or weaknesses

Organize your answer under these four headings. Be specific and only base your
analysis on the document content.

DOCUMENT:
{text}

RESEARCH GAP ANALYSIS:"""


def presentation_prompt(text: str, num_slides: int = 8) -> str:
    return f"""Create an outline for a {num_slides}-slide presentation based on the document below.
For each slide, provide a title and 3-5 bullet points.
Return the result in this exact format for each slide:

Slide 1: <title>
- <bullet>
- <bullet>
- <bullet>

DOCUMENT:
{text}

PRESENTATION OUTLINE:"""
