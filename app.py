"""
app.py
ResearchMind AI — main Streamlit UI.

Layout: a home screen with a document upload/analyze flow and a grid of
clickable "workspace cards" (NotebookLM-style — the whole card is a button,
not a button sitting inside a card). Clicking a card navigates to that tool's
page; a Back button returns to the home grid.

This file only handles layout/navigation — all real logic lives in
document_processor.py, database.py, ai_services.py, agent_service.py, and
generators.py.
"""

import os
import streamlit as st

from constants import (
    APP_NAME, APP_ICON, APP_TAGLINE, APP_DESCRIPTION, DEVELOPER,
    SUPPORTED_FORMATS, DEFAULT_QUIZ_QUESTIONS, DEFAULT_FLASHCARDS, WORKSPACE_CARDS,
)
from utils import is_supported_file, is_file_size_valid
from document_processor import process_document
from database import DocumentDatabase
import ai_services
import agent_service
import memory_service
import generators

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title=APP_NAME, page_icon=APP_ICON, layout="wide")

# Load CSS relative to this file's location (fixes path issues on Windows/different CWDs)
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CSS_PATH = os.path.join(APP_DIR, "assets", "style.css")
if os.path.exists(CSS_PATH):
    with open(CSS_PATH) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
else:
    st.warning("style.css not found — running with default Streamlit theme.")

# ---------------- SESSION STATE ----------------
defaults = {
    "documents": {},           # doc_id -> {filename, text, word_count}
    "pending_files": {},       # doc_id -> raw bytes, waiting to be analyzed
    "active_doc_id": None,
    "view": "home",            # current page: home | chat | summary | ... | agent
    "questions_asked": 0,
    "reports_generated": 0,
    "quizzes_generated": 0,
    "chat_history": [],
    "agent_history": [],
    "planner_history": [],
    "current_quiz": None,
    "current_flashcards": None,
    "current_presentation": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

if "db" not in st.session_state:
    st.session_state.db = DocumentDatabase()

db = st.session_state.db


def go_home():
    st.session_state.view = "home"


def go(view_key):
    st.session_state.view = view_key


def offer_download(path: str, label: str = "⬇️ Download File"):
    """
    Read a generated file from server disk and offer it as a real browser
    download via st.download_button. Without this, files saved by generators.py
    only exist on the server's disk — the user has no way to actually get them,
    especially on Streamlit Cloud where the filesystem isn't user-accessible.
    """
    filename = os.path.basename(path)
    mime = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if path.endswith(".docx") else
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    with open(path, "rb") as f:
        file_bytes = f.read()
    st.download_button(label, data=file_bytes, file_name=filename, mime=mime)


# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_NAME}")
    st.caption("Intelligent Research Workspace")
    st.divider()

    st.markdown("### 📊 Quick Statistics")
    col1, col2 = st.columns(2)
    col1.metric("Files", len(st.session_state.documents))
    col2.metric("Questions", st.session_state.questions_asked)
    col1.metric("Reports", st.session_state.reports_generated)
    col2.metric("Quizzes", st.session_state.quizzes_generated)
    st.divider()

    with st.expander("📁 Supported Formats"):
        st.markdown("\n".join(f"- .{fmt}" for fmt in SUPPORTED_FORMATS))

    with st.expander("📁 Recent Documents"):
        if st.session_state.documents:
            for doc in list(st.session_state.documents.values())[-5:]:
                st.markdown(f"- {doc['filename']}")
        else:
            st.caption("No documents yet.")

    with st.expander("⚙️ Settings"):
        st.caption("AI Model: **gpt-4o-mini**")
        if st.button("Clear Chat History"):
            st.session_state.chat_history = []
            st.session_state.agent_history = []
            st.rerun()
        if st.button("Reset Workspace"):
            for doc_id in st.session_state.documents:
                memory_service.clear_memory(doc_id)
            for key in list(st.session_state.keys()):
                if key != "db":
                    del st.session_state[key]
            st.rerun()

    with st.expander("ℹ️ About"):
        st.caption(APP_DESCRIPTION)
        st.caption(f"Developed by **{DEVELOPER}**")


# =====================================================================
# HOME VIEW — upload, analyze, workspace card grid
# =====================================================================
if st.session_state.view == "home":

    st.markdown(f"""
    <div class="header-box">
        <h1>{APP_ICON} {APP_NAME}</h1>
        <p class="subtitle">{APP_TAGLINE}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f'<div class="intro-banner">{APP_DESCRIPTION}</div>', unsafe_allow_html=True)
    st.divider()

    # ---------------- UPLOAD ----------------
    st.markdown("### 📂 Upload Documents")
    uploaded_files = st.file_uploader(
        "Drag and drop files here, or click to browse",
        type=SUPPORTED_FORMATS,
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded_files:
        for file in uploaded_files:
            doc_id = file.name
            if doc_id in st.session_state.documents or doc_id in st.session_state.pending_files:
                continue
            if not is_supported_file(file.name):
                st.error(f"Unsupported file type: {file.name}")
                continue
            file_bytes = file.read()
            if not is_file_size_valid(file_bytes):
                st.error(f"File too large: {file.name}")
                continue
            st.session_state.pending_files[doc_id] = file_bytes

    st.divider()

    # ---------------- ANALYZE (with real progress steps) ----------------
    st.markdown("### 🔍 Analyze Documents")

    if st.session_state.pending_files:
        st.caption(f"{len(st.session_state.pending_files)} document(s) ready to analyze.")

        if st.button("Analyze Documents", type="primary"):
            with st.status("Analyzing documents...", expanded=True) as status:
                for doc_id, file_bytes in list(st.session_state.pending_files.items()):
                    st.write(f"📄 Reading {doc_id}...")
                    try:
                        result = process_document(doc_id, file_bytes)
                    except Exception as e:
                        st.error(f"Failed to process {doc_id}: {e}")
                        continue

                    st.write("🧠 Creating AI embeddings...")
                    st.write("📚 Building knowledge base...")
                    db.add_document(doc_id, doc_id, result["text"], pages=result.get("pages"))

                    st.session_state.documents[doc_id] = {
                        "filename": doc_id,
                        "text": result["text"],
                        "word_count": result["word_count"],
                    }
                    del st.session_state.pending_files[doc_id]

                status.update(label="✅ Analysis Complete! Your AI research assistant is ready.",
                               state="complete")
            st.rerun()
    elif not st.session_state.documents:
        st.info("Upload a document above, then click Analyze to unlock the AI workspace.")
    else:
        st.success("All uploaded documents are analyzed and ready.")

    st.divider()

    # ---------------- ACTIVE DOCUMENT SELECTOR ----------------
    has_docs = bool(st.session_state.documents)
    if has_docs:
        doc_names = {d["filename"]: doc_id for doc_id, d in st.session_state.documents.items()}
        selected_name = st.selectbox("Active document for AI tools", list(doc_names.keys()))
        st.session_state.active_doc_id = doc_names[selected_name]

    # ---------------- AI ASSISTANT SUGGESTIONS ----------------
    st.markdown("### ✨ AI Assistant Suggestions")
    if not has_docs:
        st.caption("Upload documents to unlock AI Insights.")
    else:
        sugg_cols = st.columns(3)
        suggestions = [
            "Summarize this document",
            "What are the research gaps?",
            "Quiz me on this content",
        ]
        targets = ["summary", "research_gap", "quiz"]
        for col, sugg, target in zip(sugg_cols, suggestions, targets):
            with col:
                if st.button(sugg, use_container_width=True):
                    go(target)
                    st.rerun()

    st.divider()

    # ---------------- WORKSPACE CARD GRID ----------------
    st.markdown("### 🚀 AI Workspace")
    cards_per_row = 3
    for i in range(0, len(WORKSPACE_CARDS), cards_per_row):
        row = WORKSPACE_CARDS[i:i + cards_per_row]
        cols = st.columns(cards_per_row)
        for col, (icon, title, desc, view_key) in zip(cols, row):
            with col:
                with st.container(border=True):
                    st.markdown(f'<div class="card-icon">{icon}</div>', unsafe_allow_html=True)
                    clicked = st.button(
                        title, key=f"card_{view_key}",
                        use_container_width=True, disabled=not has_docs,
                    )
                    if has_docs:
                        st.markdown(f'<div class="card-desc">{desc}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="card-locked">🔒 Analyze a document to unlock</div>',
                                    unsafe_allow_html=True)
                    if clicked:
                        go(view_key)
                        st.rerun()

# =====================================================================
# TOOL VIEWS — each has a Back button + its own logic
# =====================================================================
else:
    doc = st.session_state.documents.get(st.session_state.active_doc_id)

    st.markdown('<div class="back-link">', unsafe_allow_html=True)
    if st.button("← Back to Workspace"):
        go_home()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if not doc:
        st.warning("No active document selected. Go back and pick one.")
    else:
        active_text = doc["text"]
        selected_name = doc["filename"]
        active_doc_id = st.session_state.active_doc_id

        # ---- CHAT ----
        if st.session_state.view == "chat":
            st.markdown("## 💬 Chat with AI")
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

            question = st.chat_input("Ask something about this document...")
            if question:
                st.session_state.chat_history.append({"role": "user", "content": question})
                with st.spinner("Thinking..."):
                    chunks = db.query(question, doc_id=active_doc_id)
                    answer = ai_services.answer_question(question, chunks)
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
                st.session_state.questions_asked += 1
                st.rerun()

        # ---- SUMMARY ----
        elif st.session_state.view == "summary":
            st.markdown("## 📝 Smart Summary")
            length = st.radio("Length", ["short", "medium", "detailed"], horizontal=True, index=1)
            if st.button("Generate Summary", type="primary"):
                with st.spinner("Summarizing..."):
                    st.session_state[f"summary_{active_doc_id}"] = ai_services.generate_summary(
                        active_text, length
                    )
            summary = st.session_state.get(f"summary_{active_doc_id}")
            if summary:
                st.markdown(summary)
                if st.button("Export as DOCX"):
                    path = generators.export_summary_to_docx(summary, selected_name)
                    st.session_state.reports_generated += 1
                    offer_download(path)

        # ---- LITERATURE REVIEW ----
        elif st.session_state.view == "literature_review":
            st.markdown("## 📚 Literature Review")
            if st.button("Generate Literature Review", type="primary"):
                with st.spinner("Writing review..."):
                    st.session_state[f"litreview_{active_doc_id}"] = \
                        ai_services.generate_literature_review(active_text)
            review = st.session_state.get(f"litreview_{active_doc_id}")
            if review:
                st.markdown(review)
                if st.button("Export as DOCX"):
                    path = generators.export_literature_review_to_docx(review, selected_name)
                    st.session_state.reports_generated += 1
                    offer_download(path)

        # ---- FLASHCARDS ----
        elif st.session_state.view == "flashcards":
            st.markdown("## 🧠 Flashcards")
            num_cards = st.slider("Number of flashcards", 5, 25, DEFAULT_FLASHCARDS)
            if st.button("Generate Flashcards", type="primary"):
                with st.spinner("Creating flashcards..."):
                    st.session_state.current_flashcards = ai_services.generate_flashcards(
                        active_text, num_cards
                    )
            if st.session_state.current_flashcards:
                card_cols = st.columns(2)
                for i, card in enumerate(st.session_state.current_flashcards):
                    with card_cols[i % 2]:
                        with st.expander(f"🗂️ {card['front']}"):
                            st.write(card["back"])
                if st.button("Export as DOCX"):
                    path = generators.export_flashcards_to_docx(
                        st.session_state.current_flashcards, selected_name
                    )
                    st.session_state.reports_generated += 1
                    offer_download(path)

        # ---- QUIZ ----
        elif st.session_state.view == "quiz":
            st.markdown("## ❓ AI Quiz")
            num_q = st.slider("Number of questions", 3, 15, DEFAULT_QUIZ_QUESTIONS)
            if st.button("Generate Quiz", type="primary"):
                with st.spinner("Creating quiz..."):
                    st.session_state.current_quiz = ai_services.generate_quiz(active_text, num_q)
                    st.session_state.quizzes_generated += 1
            if st.session_state.current_quiz:
                for i, q in enumerate(st.session_state.current_quiz, start=1):
                    st.markdown(f"**Q{i}: {q['question']}**")
                    for letter, option in q["options"].items():
                        st.write(f"{letter}) {option}")
                    with st.expander("Show answer"):
                        st.write(f"Correct answer: {q['correct']}")
                if st.button("Export as DOCX"):
                    path = generators.export_quiz_to_docx(st.session_state.current_quiz, selected_name)
                    st.session_state.reports_generated += 1
                    offer_download(path)

        # ---- PRESENTATION ----
        elif st.session_state.view == "presentation":
            st.markdown("## 🎞 AI Presentation Studio")
            num_slides = st.slider("Number of slides", 4, 15, 8)
            if st.button("Generate Outline", type="primary"):
                with st.spinner("Building outline..."):
                    st.session_state.current_presentation = \
                        ai_services.generate_presentation_outline(active_text, num_slides)
            slides = st.session_state.current_presentation
            if slides:
                for slide in slides:
                    st.markdown(f"**{slide['title']}**")
                    for bullet in slide["bullets"]:
                        st.write(f"- {bullet}")
                if st.button("Export as PPTX"):
                    path = generators.export_presentation_to_pptx(slides, title=selected_name)
                    st.session_state.reports_generated += 1
                    offer_download(path)

        # ---- PLANNER AGENT ----
        elif st.session_state.view == "planner":
            st.markdown("## 🧭 Planner Agent")
            st.caption("Ask anything about this document — the Planner classifies your "
                       "intent and automatically routes to the right agent (Recommendation, "
                       "Timeline, Innovation, Research Gap, Citation, or general Chat).")

            for msg in st.session_state.get("planner_history", []):
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

            question = st.chat_input("Ask the Planner Agent...")
            if question:
                if "planner_history" not in st.session_state:
                    st.session_state.planner_history = []
                st.session_state.planner_history.append({"role": "user", "content": question})

                with st.spinner("Classifying intent → routing → generating..."):
                    topic = ai_services.extract_topic(active_text)
                    gaps = st.session_state.get(f"gaps_{active_doc_id}", "")
                    routed = agent_service.run_planner_agent(
                        db, question, active_doc_id, topic=topic, research_gaps=gaps
                    )

                intent = routed["intent"]
                result = routed["result"]
                # Each intent's result dict has a different shape — surface the right field.
                answer_text = (
                    result.get("answer") or result.get("recommendations") or
                    result.get("timeline") or result.get("ideas") or result.get("gaps") or
                    "No response generated."
                )
                display_text = f"*Routed to: **{intent}***\n\n{answer_text}"

                st.session_state.planner_history.append(
                    {"role": "assistant", "content": display_text}
                )
                st.session_state.questions_asked += 1
                st.rerun()

        # ---- CITATION AGENT ----
        elif st.session_state.view == "citation":
            st.markdown("## 📖 Citation Agent")
            st.caption("Answers with page numbers and a similarity-based confidence score. "
                       "Page numbers are only available for PDF uploads.")

            question = st.text_input("Ask a question that needs a precise, cited answer:")
            if st.button("Get Cited Answer", type="primary") and question:
                with st.spinner("Retrieving passages → scoring confidence → answering..."):
                    result = agent_service.run_citation_agent(db, question, active_doc_id)

                st.markdown(result["answer"])
                if result["citations"]:
                    st.markdown("**Citations:**")
                    for c in result["citations"]:
                        page_label = f"Page {c['page']}" if c["page"] else "Page N/A (non-PDF)"
                        st.markdown(f"- {page_label} — confidence: {c['confidence']}%")
                        with st.expander("View excerpt"):
                            st.caption(c["text"])
                else:
                    st.info("No matching passages found for this question.")

        # ---- PROPOSAL AGENT ----
        elif st.session_state.view == "proposal":
            st.markdown("## 🎓 Proposal Agent")
            st.caption("Drafts an original research proposal inspired by this document's topic.")

            degree = st.selectbox("Degree level", ["BS", "MS", "PhD"])
            university = st.text_input("University name", value="University of Sindh")

            if st.button("Generate Proposal", type="primary"):
                with st.spinner("Drafting proposal..."):
                    st.session_state[f"proposal_{active_doc_id}"] = ai_services.generate_proposal(
                        active_text, degree, university
                    )

            proposal = st.session_state.get(f"proposal_{active_doc_id}")
            if proposal:
                st.markdown(proposal)
                if st.button("Export as DOCX"):
                    path = generators.export_proposal_to_docx(proposal, selected_name)
                    st.session_state.reports_generated += 1
                    offer_download(path)

        # ---- RESEARCH GAP ----
        elif st.session_state.view == "research_gap":
            st.markdown("## 🔬 Research Gap Finder")
            if st.button("Detect Research Gaps", type="primary"):
                with st.spinner("Analyzing gaps..."):
                    st.session_state[f"gaps_{active_doc_id}"] = \
                        ai_services.detect_research_gaps(active_text)
            gaps = st.session_state.get(f"gaps_{active_doc_id}")
            if gaps:
                st.markdown(gaps)
                if st.button("Export as DOCX"):
                    path = generators.export_research_gap_to_docx(gaps, selected_name)
                    st.session_state.reports_generated += 1
                    offer_download(path)

        # ---- RESEARCH AGENT ----
        elif st.session_state.view == "agent":
            st.markdown("## 🤖 Research Agent")
            st.caption("Combines your document with live arXiv + Semantic Scholar search, "
                       "and cites every source it uses.")

            for msg in st.session_state.agent_history:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

            question = st.chat_input("Ask the Research Agent...")
            if question:
                st.session_state.agent_history.append({"role": "user", "content": question})
                with st.spinner("Planning → retrieving → searching → synthesizing..."):
                    result = agent_service.run_research_agent(db, question, active_doc_id)

                answer_with_sources = result["answer"]
                if result["sources"]:
                    answer_with_sources += "\n\n**Sources found online:**\n"
                    for s in result["sources"]:
                        answer_with_sources += f"- [{s['source']}] [{s['title']}]({s['url']})\n"

                st.session_state.agent_history.append(
                    {"role": "assistant", "content": answer_with_sources}
                )
                st.session_state.questions_asked += 1
                st.rerun()

        # ---- RECOMMENDATION AGENT ----
        elif st.session_state.view == "recommendation":
            st.markdown("## ⭐ Recommendation Agent")
            st.caption("Searches Semantic Scholar for your document's topic and recommends "
                       "what to look into next.")
            if st.button("Get Recommendations", type="primary"):
                with st.spinner("Finding topic → searching Semantic Scholar → generating recommendations..."):
                    topic = ai_services.extract_topic(active_text)
                    result = agent_service.run_recommendation_agent(topic)
                st.session_state[f"reco_{active_doc_id}"] = result

            result = st.session_state.get(f"reco_{active_doc_id}")
            if result:
                st.markdown(result["recommendations"])
                if result["sources"]:
                    with st.expander("Sources used"):
                        for s in result["sources"]:
                            st.markdown(f"- [{s['title']}]({s['url']}) ({s.get('year', 'n.d.')})")
                else:
                    st.caption("⚠️ Semantic Scholar returned no results — this is usually a "
                              "temporary rate limit on their free API, not a bug. Wait "
                              "10-15 seconds and click the button again.")

        # ---- TIMELINE AGENT ----
        elif st.session_state.view == "timeline":
            st.markdown("## 📈 Timeline Agent")
            st.caption("Searches Semantic Scholar and builds a chronological timeline "
                       "of how your document's topic evolved.")
            if st.button("Build Timeline", type="primary"):
                with st.spinner("Finding topic → searching papers by year → building timeline..."):
                    topic = ai_services.extract_topic(active_text)
                    result = agent_service.run_timeline_agent(topic)
                st.session_state[f"timeline_{active_doc_id}"] = result

            result = st.session_state.get(f"timeline_{active_doc_id}")
            if result:
                st.markdown(result["timeline"])
                if result["sources"]:
                    with st.expander("Sources used"):
                        for s in result["sources"]:
                            st.markdown(f"- {s['year']} — [{s['title']}]({s['url']})")
                else:
                    st.caption("⚠️ Semantic Scholar returned no results — this is usually a "
                              "temporary rate limit on their free API, not a bug. Wait "
                              "10-15 seconds and click the button again.")

        # ---- INNOVATION AGENT ----
        elif st.session_state.view == "innovation":
            st.markdown("## 💡 Innovation Agent")
            st.caption("Combines this document's Research Gap analysis with recent trends "
                       "found online to suggest novel project ideas.")

            gaps = st.session_state.get(f"gaps_{active_doc_id}")
            if not gaps:
                st.info("Run Research Gap Finder first — the Innovation Agent builds on "
                        "that analysis.")
            else:
                if st.button("Generate Novel Ideas", type="primary"):
                    with st.spinner("Finding topic → searching recent trends → generating ideas..."):
                        topic = ai_services.extract_topic(active_text)
                        result = agent_service.run_innovation_agent(gaps, topic)
                    st.session_state[f"innovation_{active_doc_id}"] = result

                result = st.session_state.get(f"innovation_{active_doc_id}")
                if result:
                    st.markdown(result["ideas"])
                    if result["sources"]:
                        with st.expander("Sources used"):
                            for s in result["sources"]:
                                st.markdown(f"- [{s['title']}]({s['url']}) ({s.get('year', 'n.d.')})")

        # ---- EXPORT WORKSPACE ----
        elif st.session_state.view == "export":
            st.markdown("## 📤 Export Workspace")
            st.caption("Bundles everything generated for this document into one report.")

            reco = st.session_state.get(f"reco_{active_doc_id}")
            timeline = st.session_state.get(f"timeline_{active_doc_id}")
            innovation = st.session_state.get(f"innovation_{active_doc_id}")
            proposal = st.session_state.get(f"proposal_{active_doc_id}")

            sections = {
                "Summary": st.session_state.get(f"summary_{active_doc_id}"),
                "Literature Review": st.session_state.get(f"litreview_{active_doc_id}"),
                "Research Gap Analysis": st.session_state.get(f"gaps_{active_doc_id}"),
                "Recommendations": reco["recommendations"] if reco else None,
                "Research Timeline": timeline["timeline"] if timeline else None,
                "Novel Project Ideas": innovation["ideas"] if innovation else None,
                "Research Proposal": proposal,
            }
            available = {k: v for k, v in sections.items() if v}

            if not available:
                st.info("Nothing generated yet for this document — visit Summary, "
                        "Literature Review, or Research Gap first.")
            else:
                st.write(f"Ready to export: {', '.join(available.keys())}")
                if st.button("Export Full Report as DOCX", type="primary"):
                    path = generators.export_workspace_bundle(selected_name, available)
                    st.session_state.reports_generated += 1
                    offer_download(path)
