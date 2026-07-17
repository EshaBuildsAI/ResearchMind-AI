# 🧠 ResearchMind AI

AI-powered workspace for intelligent document analysis, research assistance, and
knowledge discovery. Built for students and researchers who want one place to
upload a paper and get summaries, quizzes, flashcards, presentations, and a real
research agent — without juggling five different tools.

---

## ✨ Features

### 📂 Upload & Analyze
- Drag-and-drop upload for PDF, DOCX, PPTX, XLSX, TXT
- Real analyze step with live progress: reading → embedding → knowledge base → done
- Multiple documents supported, switch between them anytime

### 🚀 AI Workspace (NotebookLM-style clickable cards)
| Card | What it does |
|---|---|
| 💬 Chat with AI | Ask questions, answered using RAG over the active document |
| 📝 Smart Summary | Short / medium / detailed structured summaries |
| 📚 Literature Review | Auto-generates Introduction, Related Work, Critical Analysis, Conclusion |
| 🧠 Flashcards | Auto-generated front/back study cards |
| ❓ AI Quiz | Multiple-choice questions with an answer key |
| 🎞 AI Presentation Studio | Slide-by-slide outline, exportable as real .pptx |
| 🔬 Research Gap Finder | Missing topics, future work, dataset & methodology gaps |
| 🤖 Research Agent | Multi-step agent: doc retrieval + arXiv + Semantic Scholar, cited answers |
| 📤 Export Workspace | Bundles everything generated for a document into one DOCX report |

Cards stay locked until a document is uploaded **and** analyzed — no dead buttons.

### 🤖 Research Agent (real agentic AI, not a single prompt)
Built with **LangGraph** as an explicit 3-node pipeline:
1. `retrieve_docs` — pulls relevant chunks from the active document (ChromaDB)
2. `search_web` — queries **arXiv** and **Semantic Scholar** (both free, no API key)
3. `synthesize` — combines both sources into one answer with inline citations

This is genuine tool-calling orchestration — every step is inspectable, and it
fails gracefully (if the web search is down, it still answers from the document).

### 🎨 UI
- Teal + coral theme throughout
- Whole-card hover elevation animation (not a button *inside* a card — the card
  itself is the clickable surface)
- Sidebar: Quick Statistics, Supported Formats, Recent Documents, Settings, About

---

## 🔄 System Workflow

```
Upload (drag & drop)
      ↓
Document Processor  → extracts raw text (PyMuPDF / python-docx / python-pptx / pandas)
      ↓
Database (ChromaDB)  → chunks text, stores embeddings (RAG-ready)
      ↓
AI Services (Gemini)  → summary / chat / quiz / flashcards / literature review / gaps
      ↓                              ↘
Generators              Agent Service (LangGraph: doc retrieval + arXiv + Semantic Scholar)
(DOCX / PPTX export)                  ↓
      ↓                          Cited answer
Exports folder
```

**Chat / Research Agent question flow:**
```
User question
      ↓
Retrieve relevant chunks (ChromaDB similarity search)
      ↓
[Research Agent only] Search arXiv + Semantic Scholar
      ↓
Gemini synthesizes an answer from the combined context
      ↓
Answer shown in chat (+ sources, for the Agent)
```

---

## 📁 Folder Structure

```
researchmind/
├── app.py                 # Main UI — layout & navigation only
├── constants.py            # App config, colors, model name, workspace card list
├── utils.py                 # File validation, text cleaning, chunking helpers
├── document_processor.py     # Text extraction (PDF/DOCX/PPTX/XLSX/TXT)
├── database.py                # ChromaDB — chunking, embeddings, retrieval (RAG)
├── prompts.py                  # All prompt templates, centralized
├── ai_services.py               # Gemini API calls (summary/chat/quiz/flashcards/gaps)
├── agent_service.py              # Research Assistant Agent (LangGraph + free APIs)
├── generators.py                  # Export to DOCX/PPTX
├── assets/style.css                # Teal + coral theme, card animations
├── uploads/                          # (optional) raw file storage
├── exports/                           # Generated reports land here
├── chroma_db/                          # Persistent vector database (auto-created)
├── requirements.txt
├── roadmap.md                          # Honest V1/V2/V3 feature roadmap
└── README.md
```

Each file has one job — UI, extraction, storage, prompts, AI calls, agent
orchestration, and exports are all kept separate so any one piece can be
swapped or tested on its own.

---

## ⚙️ Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Get a free Gemini API key: https://aistudio.google.com/apikey
   (Create key → choose "Default Gemini Project" → copy the key)

3. Create a `.env` file in the project root:
   ```
   GEMINI_API_KEY=your_key_here
   ```

4. Run the app:
   ```
   streamlit run app.py
   ```

---

## 🧰 Tech Stack

Python · Streamlit · Google Gemini API (`gemini-2.5-flash`) · ChromaDB ·
LangGraph · PyMuPDF · python-docx · python-pptx · pandas · openpyxl ·
arXiv API · Semantic Scholar API

---

## 🗺️ Roadmap

V1 (this build) is fully working — see `roadmap.md` for what's planned next
(Planner Agent, Citation Agent with confidence scores, Recommendation Agent,
Timeline Agent, Proposal Agent, multi-modal document processing, and more).

---

**Developed by Esha Meo**
