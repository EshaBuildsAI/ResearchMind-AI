"""
constants.py
Central configuration for ResearchMind AI.
All fixed values (app info, colors, models, limits) live here.
"""

# ---------------- APP INFO ----------------
APP_NAME = "ResearchMind AI"
APP_ICON = "🧠"
APP_TAGLINE = "Upload • Analyze • Discover Research Insights"
APP_DESCRIPTION = (
    "AI-powered workspace for intelligent document analysis, "
    "research assistance and knowledge discovery."
)
DEVELOPER = "Esha Meo"

# ---------------- THEME COLORS ----------------
COLOR_TEAL_DARK = "#0f4c4c"
COLOR_TEAL = "#12726b"
COLOR_TEAL_LIGHT = "#e6f2f1"
COLOR_CORAL = "#ff6f5e"
COLOR_CORAL_DARK = "#e85a49"
COLOR_BG = "#f6faf9"

# ---------------- FILE HANDLING ----------------
SUPPORTED_FORMATS = ["pdf", "docx", "pptx", "xlsx", "txt"]
UPLOAD_DIR = "uploads"
EXPORT_DIR = "exports"
MAX_FILE_SIZE_MB = 50

# ---------------- CHUNKING (for RAG) ----------------
CHUNK_SIZE = 1000        # characters per chunk
CHUNK_OVERLAP = 150      # overlap between chunks
TOP_K_RESULTS = 5        # chunks retrieved per query

# ---------------- DATABASE ----------------
CHROMA_DB_PATH = "chroma_db"
CHROMA_COLLECTION_NAME = "researchmind_documents"

# ---------------- AI MODEL ----------------
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"

# ---------------- FREE RESEARCH APIs (no key required) ----------------
ARXIV_API_URL = "http://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

# ---------------- WORKSPACE CARDS (home screen grid) ----------------
# Each: (icon, title, description, view_key)
WORKSPACE_CARDS = [
    ("💬", "Chat with AI", "Ask questions about your document", "chat"),
    ("📝", "Smart Summary", "Get a structured summary", "summary"),
    ("📚", "Literature Review", "Auto-generate a review section", "literature_review"),
    ("🧠", "Flashcards", "Study key concepts and terms", "flashcards"),
    ("❓", "AI Quiz", "Test your understanding", "quiz"),
    ("🎞", "AI Presentation Studio", "Turn research into slides", "presentation"),
    ("🔬", "Research Gap Finder", "Find missing topics & limitations", "research_gap"),
    ("🤖", "Research Agent", "Doc + web search, cited answers", "agent"),
    ("📤", "Export Workspace", "Download everything as one report", "export"),
]

# ---------------- GENERATION DEFAULTS ----------------
DEFAULT_SUMMARY_LENGTH = "medium"      # short | medium | detailed
DEFAULT_QUIZ_QUESTIONS = 5
DEFAULT_FLASHCARDS = 10
