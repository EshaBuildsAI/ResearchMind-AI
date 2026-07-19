"""
knowledge_graph_service.py
Builds a visual knowledge graph of a document's key concepts and how they
relate — a real graph (networkx + matplotlib), not a static illustration.
The concepts/relationships come from the AI reading the document; the graph
layout and rendering is deterministic, real graph theory (force-directed
spring layout), not AI-drawn.
"""

import io
import json
import re

import matplotlib
matplotlib.use("Agg")  # headless rendering — required for Streamlit Cloud (no display)
import matplotlib.pyplot as plt
import networkx as nx

import ai_services
from prompts import knowledge_graph_prompt
from logger import log_error, log_info


def _parse_graph_json(raw: str) -> dict:
    """Parse the AI's JSON response, tolerating minor formatting issues
    (e.g. stray markdown code fences) rather than failing outright."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        log_error("Knowledge graph JSON parse failed", e)
        return {"concepts": [], "edges": []}

    return {
        "concepts": data.get("concepts", []),
        "edges": data.get("edges", []),
    }


def extract_graph_data(text: str) -> dict:
    """Ask the AI to extract concepts and relationships from the document.
    Returns {"concepts": [...], "edges": [{"from", "to", "relation"}, ...]}."""
    raw = ai_services._generate(knowledge_graph_prompt(text))
    return _parse_graph_json(raw)


def render_graph(graph_data: dict) -> bytes:
    """Render the concept graph to a PNG image using networkx + matplotlib.
    Returns PNG bytes, ready for st.image()."""
    concepts = graph_data.get("concepts", [])
    edges = graph_data.get("edges", [])

    if not concepts:
        raise ValueError("No concepts were extracted from this document.")

    graph = nx.DiGraph()
    graph.add_nodes_from(concepts)

    for edge in edges:
        source, target = edge.get("from"), edge.get("to")
        if source in concepts and target in concepts:
            graph.add_edge(source, target, label=edge.get("relation", ""))

    fig, ax = plt.subplots(figsize=(11, 8))
    pos = nx.spring_layout(graph, k=1.2, seed=42)  # seed = reproducible layout

    nx.draw_networkx_nodes(graph, pos, node_color="#e6f2f1",
                            edgecolors="#12726b", linewidths=2,
                            node_size=2600, ax=ax)
    nx.draw_networkx_labels(graph, pos, font_size=9, font_color="#0f4c4c",
                             font_weight="bold", ax=ax)
    nx.draw_networkx_edges(graph, pos, edge_color="#ff6f5e", arrows=True,
                            arrowsize=15, width=1.5, ax=ax,
                            connectionstyle="arc3,rad=0.1")

    edge_labels = nx.get_edge_attributes(graph, "label")
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels,
                                  font_size=7, font_color="#5a6d6c", ax=ax)

    ax.axis("off")
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)

    log_info(f"Knowledge graph rendered: {len(concepts)} concepts, {len(edges)} edges")
    return buffer.getvalue()


def build_knowledge_graph(text: str) -> dict:
    """Public entry point: extracts concepts via AI, renders the graph.
    Returns {"image_bytes": bytes, "concepts": [...], "edges": [...]}."""
    graph_data = extract_graph_data(text)
    image_bytes = render_graph(graph_data)
    return {
        "image_bytes": image_bytes,
        "concepts": graph_data["concepts"],
        "edges": graph_data["edges"],
    }
