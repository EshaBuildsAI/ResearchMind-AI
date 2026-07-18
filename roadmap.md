# ResearchMind AI — Roadmap

Being upfront about what's real vs planned, so the portfolio story stays honest.

## ✅ V1 — Built and working now

**Core:**
- Professional UI (NotebookLM-style clickable workspace cards, teal + coral theme)
- RAG pipeline (ChromaDB chunking + retrieval, page-aware for PDFs)
- Real download flow (server-generated files served via `st.download_button`)
- Duplicate-upload handling (re-analyzing a file replaces old data, doesn't stack)

**Content tools:**
AI Chat, Smart Summary, Literature Review, Flashcards, Quiz, AI Presentation Studio,
Research Gap Detection, Export Workspace (combined DOCX report)

**Agents (all genuinely tool-calling, not single-prompt stubs):**
- **Research Agent** — LangGraph pipeline: doc retrieval → arXiv search →
  Semantic Scholar search → cited synthesis. Now also reads/writes **persistent
  memory** (see below) so it recalls earlier questions about a document.
- **Recommendation Agent** — extracts the document's topic, searches Semantic
  Scholar, recommends techniques/papers grounded in the actual results.
- **Timeline Agent** — searches Semantic Scholar sorted by year, builds a real
  chronological view instead of a guessed one.
- **Innovation Agent** — combines a generated Research Gap analysis with fresh
  Semantic Scholar trend search to propose novel project ideas.
- **Planner Agent** — a real LangGraph `StateGraph` with **conditional edges**:
  classifies the user's question into an intent (recommendation / timeline /
  innovation / research_gap / citation / general_chat) and routes to the
  matching agent automatically. This is genuine data-dependent routing, not a
  fixed sequence of steps.
- **Citation Agent** — for PDFs, chunks are stored per-page (not just per-document),
  so answers cite a real page number. Confidence score is a similarity-based
  approximation (`1 - vector distance`, 0-100%) — explicitly documented as *not*
  a calibrated probability, just a rough closeness signal.
- **Proposal Agent** — drafts an original BS/MS/PhD research proposal (Title,
  Introduction, Problem Statement, Objectives, Literature Review, Methodology,
  Expected Outcomes, Timeline) inspired by the uploaded document's topic.
- **Smart Memory** — a JSON file per document (`memory/<doc_id>.json`) storing
  the last 20 Q&A pairs, read/written by the Research Agent. Persists across
  app restarts, unlike `st.session_state`. Deliberately simple — a file, not a
  database — and documented as such rather than oversold as a full memory system.

## 🚧 Known limitations (stated honestly, not hidden)
- Citation confidence scores are a rough embedding-distance signal, not a
  verified accuracy measure — they should be read as "how close" not "how correct"
- Page-level citation only works for PDF uploads (DOCX/PPTX/XLSX/TXT don't have
  a real page concept, so citations from those show "Page N/A")
- Semantic Scholar's free, keyless tier has a shared rate limit — Recommendation,
  Timeline, and Innovation agents can occasionally return "no results" if the
  shared quota is hit. An optional `SEMANTIC_SCHOLAR_API_KEY` env var gives a
  dedicated quota when set, but works without one too.
- Smart Memory is a flat JSON file, not a vector-searchable memory — it's
  recency-based (last 20 entries), not relevance-based

## 🌍 V2 — Not built yet
- Multi-modal processor (images, audio, video, web pages — not just documents)
- Knowledge graph across all uploaded documents
- Voice research assistant
- Broader live research beyond arXiv/Semantic Scholar (e.g. OpenAlex, CrossRef)
- Collaboration features (shared workspaces)
- Automated tests / evals (none exist yet — see project ownership notes)
- Structured logging (currently just Streamlit UI messages + console prints)

## Why this split
Recruiters can tell the difference between "I built 7 working agents with real
tool calls and conditional routing" and "I have 7 buttons labeled Agent that
call the same prompt." Every agent listed under V1 does a genuine retrieval or
API call before generating — none of them are prompts pretending to be agents.
