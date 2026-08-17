"""Corpus Index Manager and Search Orchestrator."""

import json
from pathlib import Path
from typing import List, Dict, Optional, Union
from app.config import settings, SOURCES_DIR, INDEX_DIR
from app.models.document import Document, Chunk, ScoredChunk
from app.ingestion.loader import DocumentLoader
from app.retrieval.hybrid import HybridRetriever


class CorpusIndex:
    """Manages ingestion, persistent storage, and hybrid querying over all documents."""

    def __init__(
        self,
        sources_dir: Path = SOURCES_DIR,
        index_dir: Path = INDEX_DIR,
        loader: Optional[DocumentLoader] = None,
        retriever: Optional[HybridRetriever] = None
    ):
        self.sources_dir = sources_dir
        self.index_dir = index_dir
        self.loader = loader or DocumentLoader()
        self.retriever = retriever or HybridRetriever()
        
        self.documents: Dict[str, Document] = {}
        self.chunks: List[Chunk] = []
        self.chunk_lookup: Dict[str, Chunk] = {}

    def build_from_sources(self) -> int:
        """Loads all documents from sources directory and fits the hybrid index."""
        docs = self.loader.load_directory(self.sources_dir)
        return self.index_documents(docs)

    def index_documents(self, documents: List[Document]) -> int:
        """Indexes a list of documents into memory and the hybrid retriever."""
        self.documents = {doc.metadata.doc_id: doc for doc in documents}
        self.chunks = []
        self.chunk_lookup = {}

        for doc in documents:
            for chunk in doc.chunks:
                self.chunks.append(chunk)
                self.chunk_lookup[chunk.chunk_id] = chunk

        # Fit hybrid retrieval engine
        self.retriever.fit(self.chunks)
        self._save_index_metadata()
        return len(self.chunks)

    def add_document(self, doc: Document) -> int:
        """Adds a single new or uploaded document to the index and refits."""
        self.documents[doc.metadata.doc_id] = doc
        # Re-index all active documents
        return self.index_documents(list(self.documents.values()))

    def search(
        self,
        query: str,
        top_k: int = settings.TOP_K_CHUNKS,
        doc_filter: Optional[List[str]] = None
    ) -> List[ScoredChunk]:
        """Queries the hybrid retrieval engine."""
        return self.retriever.search(query, top_k=top_k, doc_filter=doc_filter)

    def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        """Retrieves a single chunk by chunk ID."""
        return self.chunk_lookup.get(chunk_id)

    def get_document(self, doc_id: str) -> Optional[Document]:
        """Retrieves a document by document ID."""
        return self.documents.get(doc_id)

    def list_documents(self) -> List[Dict]:
        """Returns summary list of all indexed documents."""
        summaries = []
        for doc_id, doc in self.documents.items():
            summaries.append({
                "doc_id": doc_id,
                "title": doc.metadata.title,
                "source_type": doc.metadata.source_type,
                "word_count": doc.metadata.word_count,
                "chunk_count": len(doc.chunks),
                "author": doc.metadata.author,
                "created_at": doc.metadata.created_at.isoformat()
            })
        return summaries

    def _save_index_metadata(self) -> None:
        """Persists lightweight index summary to disk."""
        meta_file = self.index_dir / "index_meta.json"
        meta = {
            "total_documents": len(self.documents),
            "total_chunks": len(self.chunks),
            "documents": [
                {
                    "doc_id": doc.metadata.doc_id,
                    "title": doc.metadata.title,
                    "chunks": len(doc.chunks)
                }
                for doc in self.documents.values()
            ]
        }
        try:
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Warning: Could not save index metadata: {e}")
