"""Pydantic schemas for Document Ingestion and Chunks."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


def utc_now():
    return datetime.now(timezone.utc)


class DocumentMetadata(BaseModel):
    """Metadata describing a source document."""
    doc_id: str = Field(..., description="Unique document identifier (slug or filename)")
    title: str = Field(..., description="Human-readable title of the document")
    source_type: str = Field(..., description="Format: pdf, markdown, text, web, etc.")
    source_path: Optional[str] = Field(None, description="Local or remote path to original file")
    author: Optional[str] = Field("Unknown", description="Author or publishing entity")
    date_published: Optional[str] = Field(None, description="Publication date if known")
    word_count: int = Field(0, description="Total word count of raw document")
    char_count: int = Field(0, description="Total character count")
    created_at: datetime = Field(default_factory=utc_now)


class Chunk(BaseModel):
    """A discrete, indexed segment of a source document."""
    chunk_id: str = Field(..., description="Globally unique chunk ID, e.g. doc1#c001")
    doc_id: str = Field(..., description="Parent document identifier")
    title: str = Field(..., description="Document title")
    section: str = Field("General", description="Section header or chapter title")
    chunk_index: int = Field(..., description="Zero-indexed position in document")
    page_number: Optional[int] = Field(None, description="Page number if derived from PDF")
    char_start: int = Field(0, description="Character start offset in original document")
    char_end: int = Field(0, description="Character end offset in original document")
    text: str = Field(..., description="Raw text content of the chunk")
    token_count: Optional[int] = Field(None, description="Estimated token count")


class Document(BaseModel):
    """Full document representation containing raw text and decomposed chunks."""
    metadata: DocumentMetadata
    raw_text: str
    chunks: List[Chunk] = Field(default_factory=list)


class ScoredChunk(BaseModel):
    """A chunk enriched with retrieval similarity scores."""
    chunk: Chunk
    score: float = Field(..., description="Combined hybrid similarity score (0.0 to 1.0)")
    bm25_score: Optional[float] = Field(None, description="Raw BM25 lexical score")
    dense_score: Optional[float] = Field(None, description="Dense cosine similarity score")
    rank: int = Field(1, description="Rank in retrieval result set (1-indexed)")
