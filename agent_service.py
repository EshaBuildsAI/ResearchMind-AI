"""
agent_service.py
Research Assistant Agent — the agentic "wow factor" feature.

Given a question, this agent runs a real multi-step LangGraph pipeline:
  1. retrieve_docs  -> pulls relevant chunks from the uploaded document (database.py)
  2. search_web     -> queries arXiv + Semantic Scholar (both free, no API key)
  3. synthesize      -> combines both sources and asks Gemini for a cited answer

This is genuine tool-calling orchestration (each step is an inspectable graph node),
not a single prompt pretending to be an agent. Only free, keyless APIs are used.
"""

import os
import re
import time
import xml.etree.ElementTree as ET
from typing import TypedDict, List

import requests
from langgraph.graph import StateGraph, END

import ai_services
from database import DocumentDatabase
from constants import ARXIV_API_URL, SEMANTIC_SCHOLAR_API_URL, SEMANTIC_SCHOLAR_API_KEY_ENV
from prompts import (
    recommendation_prompt, timeline_prompt, innovation_prompt,
    citation_answer_prompt, planner_intent_prompt,
)
import memory_service


def _semantic_scholar_headers() -> dict:
    """Build request headers for Semantic Scholar. Adds the API key if the user
    has set SEMANTIC_SCHOLAR_API_KEY in .env / Streamlit secrets — this gives a
    dedicated (non-shared) rate limit. Works fine without a key too; it just
    falls back to the shared free-tier limit, which can occasionally 429."""
    headers = {"User-Agent": "ResearchMindAI/1.0 (educational project)"}

    api_key = os.environ.get(SEMANTIC_SCHOLAR_API_KEY_ENV)
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get(SEMANTIC_SCHOLAR_API_KEY_ENV)
        except Exception:
            pass

    if api_key:
        headers["x-api-key"] = api_key

    return headers


# ---------------- AGENT STATE ----------------
class AgentState(TypedDict):
    question: str
    doc_id: str
    doc_context: List[str]
    web_results: List[dict]   # each: {title, url, snippet, source}
    answer: str


# ---------------- TOOLS (free, keyless APIs) ----------------

def _sanitize_search_query(query: str, max_words: int = 12) -> str:
    """
    Clean a query before sending it to Semantic Scholar / OpenAlex.

    Both APIs treat characters like ? and * as search wildcards, not literal
    punctuation — a normal user question like "What is CNN used for?" gets
    rejected by OpenAlex as a malformed wildcard query. This strips anything
    that isn't a letter, number, or basic space/hyphen, and trims overly long
    questions down to their first N words (search engines match short keyword
    phrases far better than full sentences anyway).
    """
    cleaned = re.sub(r"[^\w\s-]", " ", query)  # drop ?, *, punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    words = cleaned.split()
    if len(words) > max_words:
        cleaned = " ".join(words[:max_words])

    return cleaned


def search_arxiv(query: str, max_results: int = 3) -> List[dict]:
    """Tool: search arXiv for related papers. Free, no API key required."""
    query = _sanitize_search_query(query)
    try:
        params = {"search_query": f"all:{query}", "max_results": max_results}
        response = requests.get(ARXIV_API_URL, params=params, timeout=10)
        root = ET.fromstring(response.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        results = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns).text.strip()
            link = entry.find("atom:id", ns).text.strip()
            summary = entry.find("atom:summary", ns).text.strip()
            results.append({
                "title": title, "url": link,
                "snippet": summary[:300], "source": "arXiv",
            })
        return results
    except Exception:
        return []  # fail gracefully — agent still works with doc context alone


def search_openalex(query: str, max_results: int = 5) -> List[dict]:
    """Tool: search OpenAlex for related papers. Free, no API key required,
    and has a much more generous rate limit than Semantic Scholar's shared
    keyless tier — used as a fallback when Semantic Scholar is rate-limited."""
    query = _sanitize_search_query(query)
    try:
        params = {"search": query, "per-page": max_results}
        headers = {"User-Agent": "ResearchMindAI/1.0 (educational project; mailto:researchmindai@example.com)"}
        response = requests.get("https://api.openalex.org/works", params=params,
                                 headers=headers, timeout=15)

        if response.status_code != 200:
            print(f"[OpenAlex] Non-200 response: {response.status_code} — {response.text[:300]}")
            return []

        data = response.json()
        results = []
        for work in data.get("results", []):
            results.append({
                "title": work.get("title") or "Untitled",
                "url": work.get("id", ""),
                "snippet": _openalex_abstract(work)[:300],
                "source": "OpenAlex",
                "year": work.get("publication_year"),
            })
        return results
    except Exception as e:
        print(f"[OpenAlex] Search failed: {e}")
        return []


def _openalex_abstract(work: dict) -> str:
    """OpenAlex returns abstracts as an inverted index (word -> positions)
    instead of plain text — this reconstructs a readable snippet from it."""
    inverted = work.get("abstract_inverted_index")
    if not inverted:
        return ""
    positions = {}
    for word, idxs in inverted.items():
        for idx in idxs:
            positions[idx] = word
    return " ".join(positions[i] for i in sorted(positions))


def search_related_papers(query: str, max_results: int = 5) -> List[dict]:
    """
    Unified paper search with automatic fallback:
    Semantic Scholar → OpenAlex.
    Used by Recommendation, Timeline, and Innovation agents so a single
    provider's rate limit doesn't take the whole feature down.
    """
    results = search_semantic_scholar(query, max_results)
    if results:
        return results

    print("[Fallback] Semantic Scholar returned nothing — trying OpenAlex.")
    results = search_openalex(query, max_results)
    if results:
        return results

    print("[Fallback] OpenAlex also returned nothing.")
    return []


def search_semantic_scholar(query: str, max_results: int = 5, _retrying: bool = False) -> List[dict]:
    """Tool: search Semantic Scholar for related papers. Free, no API key required.
    Retries once after a short delay if rate-limited, since Semantic Scholar's
    unauthenticated rate limit is shared across all users and often clears quickly."""
    query = _sanitize_search_query(query)
    try:
        params = {"query": query, "limit": max_results, "fields": "title,abstract,url,year"}
        headers = _semantic_scholar_headers()
        response = requests.get(
            SEMANTIC_SCHOLAR_API_URL, params=params, headers=headers, timeout=15
        )

        if response.status_code == 429:
            print("[Semantic Scholar] Rate limited (429).")
            if not _retrying:
                time.sleep(3)
                return search_semantic_scholar(query, max_results, _retrying=True)
            return []
        if response.status_code != 200:
            print(f"[Semantic Scholar] Non-200 response: {response.status_code} — {response.text[:200]}")
            return []

        data = response.json()
        results = []
        for paper in data.get("data", []):
            results.append({
                "title": paper.get("title", "Untitled"),
                "url": paper.get("url", ""),
                "snippet": (paper.get("abstract") or "")[:300],
                "source": "Semantic Scholar",
                "year": paper.get("year"),
            })
        return results
    except requests.exceptions.Timeout:
        print("[Semantic Scholar] Request timed out.")
        return []
    except Exception as e:
        print(f"[Semantic Scholar] Search failed: {e}")
        return []


# ---------------- GRAPH NODES ----------------

def _node_retrieve_docs(state: AgentState, db: DocumentDatabase) -> AgentState:
    """Node 1: pull relevant chunks from the active document."""
    state["doc_context"] = db.query(state["question"], doc_id=state["doc_id"])
    return state


def _node_search_web(state: AgentState) -> AgentState:
    """Node 2: search free scholarly APIs for related work.
    arXiv always runs. For Semantic Scholar, falls back to OpenAlex if
    rate-limited, so one provider's outage doesn't empty this node."""
    results = search_arxiv(state["question"]) + search_related_papers(state["question"])
    state["web_results"] = results
    return state


def _node_synthesize(state: AgentState) -> AgentState:
    """Node 3: combine document context + web results + persistent memory into a cited answer."""
    doc_context = "\n\n".join(state["doc_context"]) or "No relevant document context found."
    web_context = "\n\n".join(
        f"[{r['source']}] {r['title']} ({r['url']}): {r['snippet']}"
        for r in state["web_results"]
    ) or "No related papers found online."
    memory_context = memory_service.format_memory_for_prompt(state["doc_id"])
    memory_block = f"\n\n{memory_context}\n" if memory_context else ""

    prompt = f"""You are a Research Assistant Agent. Answer the question using BOTH the
document context and the related papers below. Cite sources inline by name
(e.g. "the document states..." or "according to [arXiv] Paper Title..."). Only use
information actually present below — do not invent facts or citations.
{memory_block}
DOCUMENT CONTEXT:
{doc_context}

RELATED PAPERS:
{web_context}

QUESTION:
{state['question']}

ANSWER (with inline citations):"""

    state["answer"] = ai_services._generate(prompt)
    memory_service.save_memory_entry(state["doc_id"], state["question"], state["answer"])
    return state


# ---------------- GRAPH ASSEMBLY ----------------

def _build_graph(db: DocumentDatabase):
    """Compile the 3-node LangGraph pipeline."""
    graph = StateGraph(AgentState)
    graph.add_node("retrieve_docs", lambda s: _node_retrieve_docs(s, db))
    graph.add_node("search_web", _node_search_web)
    graph.add_node("synthesize", _node_synthesize)

    graph.set_entry_point("retrieve_docs")
    graph.add_edge("retrieve_docs", "search_web")
    graph.add_edge("search_web", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


def run_research_agent(db: DocumentDatabase, question: str, doc_id: str) -> dict:
    """
    Public entry point. Runs the full agent pipeline and returns:
    {"answer": str, "sources": [{title, url, snippet, source}, ...]}
    """
    agent = _build_graph(db)
    result = agent.invoke({
        "question": question,
        "doc_id": doc_id,
        "doc_context": [],
        "web_results": [],
        "answer": "",
    })
    return {"answer": result["answer"], "sources": result["web_results"]}


# =====================================================================
# ADDITIONAL AGENTS — each does a real tool call (Semantic Scholar)
# before asking Gemini to synthesize. None of these are single-prompt
# stubs; the web_search step genuinely runs before generation.
# =====================================================================

def run_recommendation_agent(topic_query: str) -> dict:
    """
    Recommendation Agent.
    Tool call: Semantic Scholar search on the document's topic.
    Then asks Gemini to turn the actual results into ranked recommendations.
    Returns {"recommendations": str, "sources": [...]}
    """
    papers = search_related_papers(topic_query, max_results=6)

    if not papers:
        return {
            "recommendations": "No related papers could be found online right now, "
                                "so no recommendations could be generated.",
            "sources": [],
        }

    papers_text = "\n\n".join(
        f"- {p['title']} ({p['year']}): {p['snippet']}" for p in papers
    )
    recommendations = ai_services._generate(recommendation_prompt(topic_query, papers_text))
    return {"recommendations": recommendations, "sources": papers}


def run_timeline_agent(topic_query: str) -> dict:
    """
    Timeline Agent.
    Tool call: Semantic Scholar search, sorted by year.
    Then asks Gemini to organize the actual papers into a chronological timeline.
    Returns {"timeline": str, "sources": [...]}
    """
    papers = search_related_papers(topic_query, max_results=8)
    papers = [p for p in papers if p.get("year")]  # drop undated results
    papers.sort(key=lambda p: p["year"])

    if not papers:
        return {
            "timeline": "No dated papers could be found online right now, "
                        "so a timeline could not be built.",
            "sources": [],
        }

    papers_text = "\n".join(
        f"{p['year']} — {p['title']}: {p['snippet']}" for p in papers
    )
    timeline = ai_services._generate(timeline_prompt(topic_query, papers_text))
    return {"timeline": timeline, "sources": papers}


def run_innovation_agent(research_gaps_text: str, topic_query: str) -> dict:
    """
    Innovation / Ideas Agent.
    Tool call: Semantic Scholar search for recent trends on the topic.
    Then combines that with an already-generated Research Gap analysis
    (from ai_services.detect_research_gaps) to produce novel project ideas.
    Returns {"ideas": str, "sources": [...]}
    """
    papers = search_related_papers(topic_query, max_results=6)
    papers_text = "\n\n".join(
        f"- {p['title']} ({p['year']}): {p['snippet']}" for p in papers
    ) or "No related papers found online."

    ideas = ai_services._generate(innovation_prompt(research_gaps_text, papers_text))
    return {"ideas": ideas, "sources": papers}


# =====================================================================
# CITATION AGENT — page-level citations with an approximate confidence score
# =====================================================================

def run_citation_agent(db: DocumentDatabase, question: str, doc_id: str) -> dict:
    """
    Citation Agent.
    Tool call: database.query_with_metadata() — retrieves chunks WITH their
    page number and a similarity-based confidence score (not a calibrated
    probability, just how close the match is).
    Returns {"answer": str, "citations": [{page, confidence, text}, ...]}
    """
    cited_chunks = db.query_with_metadata(question, doc_id=doc_id)

    if not cited_chunks:
        return {
            "answer": "No relevant passages were found in this document for that question.",
            "citations": [],
        }

    answer = ai_services._generate(citation_answer_prompt(question, cited_chunks))
    return {"answer": answer, "citations": cited_chunks}


# =====================================================================
# PLANNER AGENT — real conditional routing (LangGraph decides the path,
# not a hardcoded if/else in the UI layer)
# =====================================================================

class PlannerState(TypedDict):
    question: str
    doc_id: str
    topic: str
    research_gaps: str
    intent: str
    result: dict


def _node_classify_intent(state: PlannerState) -> PlannerState:
    """Ask Gemini to classify the request into one category."""
    intent = ai_services._generate(planner_intent_prompt(state["question"])).strip().lower()
    valid = {"recommendation", "timeline", "innovation", "research_gap", "citation", "general_chat"}
    state["intent"] = intent if intent in valid else "general_chat"
    return state


def _route_by_intent(state: PlannerState) -> str:
    """LangGraph conditional edge — the actual routing decision happens here,
    based on the classification result, not a fixed sequence."""
    return state["intent"]


def _node_run_recommendation(state: PlannerState, db: DocumentDatabase) -> PlannerState:
    state["result"] = run_recommendation_agent(state["topic"])
    return state


def _node_run_timeline(state: PlannerState, db: DocumentDatabase) -> PlannerState:
    state["result"] = run_timeline_agent(state["topic"])
    return state


def _node_run_innovation(state: PlannerState, db: DocumentDatabase) -> PlannerState:
    state["result"] = run_innovation_agent(state["research_gaps"], state["topic"])
    return state


def _node_run_research_gap(state: PlannerState, db: DocumentDatabase) -> PlannerState:
    doc_text = db.get_full_document_text(state["doc_id"])
    gaps = ai_services.detect_research_gaps(doc_text)
    state["result"] = {"gaps": gaps}
    return state


def _node_run_citation(state: PlannerState, db: DocumentDatabase) -> PlannerState:
    state["result"] = run_citation_agent(db, state["question"], state["doc_id"])
    return state


def _node_run_general_chat(state: PlannerState, db: DocumentDatabase) -> PlannerState:
    chunks = db.query(state["question"], doc_id=state["doc_id"])
    answer = ai_services.answer_question(state["question"], chunks)
    state["result"] = {"answer": answer}
    return state


def _build_planner_graph(db: DocumentDatabase):
    graph = StateGraph(PlannerState)
    graph.add_node("classify_intent", _node_classify_intent)
    graph.add_node("recommendation", lambda s: _node_run_recommendation(s, db))
    graph.add_node("timeline", lambda s: _node_run_timeline(s, db))
    graph.add_node("innovation", lambda s: _node_run_innovation(s, db))
    graph.add_node("research_gap", lambda s: _node_run_research_gap(s, db))
    graph.add_node("citation", lambda s: _node_run_citation(s, db))
    graph.add_node("general_chat", lambda s: _node_run_general_chat(s, db))

    graph.set_entry_point("classify_intent")
    graph.add_conditional_edges("classify_intent", _route_by_intent, {
        "recommendation": "recommendation",
        "timeline": "timeline",
        "innovation": "innovation",
        "research_gap": "research_gap",
        "citation": "citation",
        "general_chat": "general_chat",
    })
    for node in ["recommendation", "timeline", "innovation", "research_gap", "citation", "general_chat"]:
        graph.add_edge(node, END)

    return graph.compile()


def run_planner_agent(db: DocumentDatabase, question: str, doc_id: str,
                       topic: str = "", research_gaps: str = "") -> dict:
    """
    Public entry point for the Planner Agent. Classifies the question's intent,
    then routes to the matching agent/tool automatically — the caller doesn't
    need to know which specific agent handles it.
    Returns {"intent": str, "result": dict} — result's shape depends on intent.
    """
    planner = _build_planner_graph(db)
    final_state = planner.invoke({
        "question": question, "doc_id": doc_id, "topic": topic,
        "research_gaps": research_gaps, "intent": "", "result": {},
    })
    return {"intent": final_state["intent"], "result": final_state["result"]}