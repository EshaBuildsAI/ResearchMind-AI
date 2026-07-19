"""
database.py
Vector storage and semantic retrieval layer using ChromaDB.
This is the RAG backbone: every document is chunked and embedded here,
and relevant chunks are retrieved for AI Q&A, summaries, and quizzes.
"""
 
# Streamlit Cloud (and some other hosts) ship an old system sqlite3 that
# ChromaDB can't use. Swap in the pysqlite3-binary wheel instead, BEFORE
# chromadb is imported anywhere. This block must stay at the very top.
try:
    __import__("pysqlite3")
    import sys
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass  # local dev on Windows/Mac usually already has a new enough sqlite3
 
# Disable ChromaDB's telemetry pings entirely. In some chromadb/posthog version
# combinations, telemetry calls raise a harmless but noisy "capture() takes 1
# positional argument" warning on every operation — this stops it at the source.
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
 
import chromadb
from chromadb.config import Settings
 
from constants import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME, TOP_K_RESULTS
from utils import chunk_text, ensure_dir
 
 
class DocumentDatabase:
    def __init__(self):
        ensure_dir(CHROMA_DB_PATH)
        self.client = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME
        )
 
    def add_document(self, doc_id: str, filename: str, text: str, pages: list = None) -> int:
        """Chunk a document's text and store embeddings. Returns chunk count.
        Always deletes any existing chunks for this doc_id first (a no-op if none
        exist), so re-analyzing a file replaces stale data instead of stacking on
        top of it. This is unconditional rather than checked, because relying on
        a get()-before-delete check proved unreliable across ChromaDB versions.
 
        If `pages` is provided (PDF only — [(page_number, text), ...]), chunks
        are created per-page so each chunk can be traced back to a real page
        number for citations. Otherwise falls back to whole-document chunking
        with no page number attached."""
        try:
            self.collection.delete(where={"doc_id": doc_id})
        except Exception:
            pass  # nothing to delete yet — expected on first-ever upload
 
        all_chunks, all_metadatas, all_ids = [], [], []
 
        if pages:
            chunk_counter = 0
            for page_num, page_text in pages:
                page_chunks = chunk_text(page_text)
                for chunk in page_chunks:
                    all_chunks.append(chunk)
                    all_metadatas.append({
                        "doc_id": doc_id, "filename": filename,
                        "chunk_index": chunk_counter, "page": page_num,
                    })
                    all_ids.append(f"{doc_id}_chunk_{chunk_counter}")
                    chunk_counter += 1
        else:
            chunks = chunk_text(text)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadatas.append({
                    "doc_id": doc_id, "filename": filename,
                    "chunk_index": i, "page": 0,  # 0 = "no page" (ChromaDB metadata can't store None)
                })
                all_ids.append(f"{doc_id}_chunk_{i}")
 
        if not all_chunks:
            return 0
 
        self.collection.add(documents=all_chunks, ids=all_ids, metadatas=all_metadatas)
        return len(all_chunks)
 
    def query(self, query_text: str, doc_id: str = None, n_results: int = TOP_K_RESULTS) -> list:
        """Retrieve the most relevant chunks for a query, optionally scoped to one document."""
        where_filter = {"doc_id": doc_id} if doc_id else None
 
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where_filter,
        )
 
        if not results["documents"]:
            return []
 
        return results["documents"][0]
 
    def query_with_metadata(self, query_text: str, doc_id: str = None,
                             n_results: int = TOP_K_RESULTS) -> list:
        """
        Like query(), but returns each chunk with its page number and an
        approximate confidence score, for use by the Citation Agent.
 
        Returns: [{"text": str, "page": int|None, "confidence": float 0-100}, ...]
 
        The confidence score is derived from ChromaDB's vector distance
        (1 - distance, clamped to 0-100%). This is a rough similarity signal,
        NOT a calibrated probability that the citation is correct — it just
        reflects how close the chunk's embedding is to the query's embedding.
        """
        where_filter = {"doc_id": doc_id} if doc_id else None
 
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
 
        if not results["documents"] or not results["documents"][0]:
            return []
 
        chunks, metadatas, distances = (
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        )
 
        output = []
        for text, meta, distance in zip(chunks, metadatas, distances):
            confidence = max(0.0, min(1.0, 1 - distance)) * 100
            output.append({
                "text": text,
                "page": meta.get("page"),
                "confidence": round(confidence, 1),
            })
        return output
 
    def get_full_document_text(self, doc_id: str) -> str:
        """Reassemble a document's full text from its stored chunks, in order."""
        results = self.collection.get(where={"doc_id": doc_id})
 
        if not results["documents"]:
            return ""
 
        paired = sorted(
            zip(results["metadatas"], results["documents"]),
            key=lambda pair: pair[0]["chunk_index"],
        )
        return " ".join(chunk for _, chunk in paired)
 
    def delete_document(self, doc_id: str):
        """Remove all chunks belonging to a document."""
        self.collection.delete(where={"doc_id": doc_id})
 
    def list_documents(self) -> list:
        """Return unique list of {doc_id, filename} stored in the database."""
        results = self.collection.get()
        seen = {}
        for meta in results.get("metadatas", []):
            seen[meta["doc_id"]] = meta["filename"]
        return [{"doc_id": k, "filename": v} for k, v in seen.items()]
 