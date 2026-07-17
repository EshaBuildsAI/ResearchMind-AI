"""
database.py
Vector storage and semantic retrieval layer using ChromaDB.
This is the RAG backbone: every document is chunked and embedded here,
and relevant chunks are retrieved for AI Q&A, summaries, and quizzes.
"""

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

    def add_document(self, doc_id: str, filename: str, text: str) -> int:
        """Chunk a document's text and store embeddings. Returns chunk count."""
        chunks = chunk_text(text)

        if not chunks:
            return 0

        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"doc_id": doc_id, "filename": filename, "chunk_index": i}
                     for i in range(len(chunks))]

        self.collection.add(documents=chunks, ids=ids, metadatas=metadatas)
        return len(chunks)

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
