# ResearchMind AI — Roadmap

Being upfront about what's real vs planned, so the portfolio story stays honest.

## ✅ V1 — Built and working now
- Professional UI (NotebookLM-style clickable workspace cards, teal + coral theme)
- RAG pipeline (ChromaDB chunking + retrieval)
- AI Chat, Smart Summary, Literature Review, Flashcards, Quiz, AI Presentation Studio
- Research Gap Detection
- Export Workspace (single combined DOCX report)
- **Research Assistant Agent** — real LangGraph pipeline: doc retrieval → arXiv search →
  Semantic Scholar search → cited synthesis. This is genuine tool-calling, not a stub.

## 🚧 V2 — Not built yet (planned, real work required)
These need actual design work before they're implemented — building them as empty
stubs would misrepresent what the app does, so they're listed here instead:
- **Planner Agent** — decomposes multi-step user requests before delegating to tools
- **Citation Agent** — per-claim citation with page number + confidence score
  (requires tighter chunk-to-page mapping than the current text-only pipeline)
- **Recommendation Agent** — suggests related papers/techniques based on document topic
- **Timeline Agent** — builds a chronological research timeline from a topic
- **Proposal Agent** — drafts a full BS/MS final year proposal
- **Innovation Agent** — combines gap detection + trend search into novel project ideas
- **Smart Memory** — persistent agent memory across sessions (needs a memory store design)

## 🌍 V3 — Longer-term
- Multi-modal processor (images, audio, video, web pages — not just documents)
- Knowledge graph across all uploaded documents
- Voice research assistant
- Live internet research beyond arXiv/Semantic Scholar (e.g. OpenAlex, CrossRef)
- Collaboration features (shared workspaces)

## Why this split
Recruiters can tell the difference between "I built a working agent with real tool
calls" and "I have 7 buttons labeled Agent that call the same prompt." One real,
demonstrable agent (V1) plus an honest, well-reasoned roadmap (V2/V3) is a stronger
portfolio signal than a pile of non-functional features.
