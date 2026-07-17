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

import xml.etree.ElementTree as ET
from typing import TypedDict, List

import requests
from langgraph.graph import StateGraph, END

import ai_services
from database import DocumentDatabase
from constants import ARXIV_API_URL, SEMANTIC_SCHOLAR_API_URL


# ---------------- AGENT STATE ----------------
class AgentState(TypedDict):
    question: str
    doc_id: str
    doc_context: List[str]
    web_results: List[dict]   # each: {title, url, snippet, source}
    answer: str


# ---------------- TOOLS (free, keyless APIs) ----------------

def search_arxiv(query: str, max_results: int = 3) -> List[dict]:
    """Tool: search arXiv for related papers. Free, no API key required."""
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


def search_semantic_scholar(query: str, max_results: int = 3) -> List[dict]:
    """Tool: search Semantic Scholar for related papers. Free, no API key required."""
    try:
        params = {"query": query, "limit": max_results, "fields": "title,abstract,url"}
        response = requests.get(SEMANTIC_SCHOLAR_API_URL, params=params, timeout=10)
        data = response.json()

        results = []
        for paper in data.get("data", []):
            results.append({
                "title": paper.get("title", "Untitled"),
                "url": paper.get("url", ""),
                "snippet": (paper.get("abstract") or "")[:300],
                "source": "Semantic Scholar",
            })
        return results
    except Exception:
        return []


# ---------------- GRAPH NODES ----------------

def _node_retrieve_docs(state: AgentState, db: DocumentDatabase) -> AgentState:
    """Node 1: pull relevant chunks from the active document."""
    state["doc_context"] = db.query(state["question"], doc_id=state["doc_id"])
    return state


def _node_search_web(state: AgentState) -> AgentState:
    """Node 2: search free scholarly APIs for related work."""
    results = search_arxiv(state["question"]) + search_semantic_scholar(state["question"])
    state["web_results"] = results
    return state


def _node_synthesize(state: AgentState) -> AgentState:
    """Node 3: combine document context + web results into a cited answer."""
    doc_context = "\n\n".join(state["doc_context"]) or "No relevant document context found."
    web_context = "\n\n".join(
        f"[{r['source']}] {r['title']} ({r['url']}): {r['snippet']}"
        for r in state["web_results"]
    ) or "No related papers found online."

    prompt = f"""You are a Research Assistant Agent. Answer the question using BOTH the
document context and the related papers below. Cite sources inline by name
(e.g. "the document states..." or "according to [arXiv] Paper Title..."). Only use
information actually present below — do not invent facts or citations.

DOCUMENT CONTEXT:
{doc_context}

RELATED PAPERS:
{web_context}

QUESTION:
{state['question']}

ANSWER (with inline citations):"""

    state["answer"] = ai_services._generate(prompt)
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
