"""Unit tests for Document Loaders and Semantic Chunkers."""

import pytest
from pathlib import Path
from app.ingestion.loader import DocumentLoader
from app.ingestion.chunker import SemanticChunker
from app.models.document import Document


def test_chunker_markdown_sections():
    """Test markdown chunking preserves section titles and creates valid chunk IDs."""
    chunker = SemanticChunker(chunk_size=300, chunk_overlap=50)
    sample_md = """# Test Document Title

## Section One: Introduction
This is the first sentence of section one. It introduces the subject matter in detail.
Here is a second sentence describing more background information.

## Section Two: Method
Here we describe the experimental methodology and parameter setup.
We evaluated accuracy across multiple trial configurations.
"""
    chunks = chunker.chunk_markdown(doc_id="test_doc", title="Test Title", content=sample_md)
    
    assert len(chunks) >= 2
    assert all(c.doc_id == "test_doc" for c in chunks)
    assert all(c.chunk_id.startswith("test_doc#c") for c in chunks)
    
    sections = [c.section for c in chunks]
    assert any("Section One" in s for s in sections)
    assert any("Section Two" in s for s in sections)


def test_loader_directory_loading(tmp_path):
    """Test loading multiple file formats from a directory."""
    doc1 = tmp_path / "article1.md"
    doc1.write_text("# Article 1\n\nContent for article one.", encoding="utf-8")
    
    doc2 = tmp_path / "notes.txt"
    doc2.write_text("Technical Notes\n\nSome plain text notes here.", encoding="utf-8")

    loader = DocumentLoader()
    documents = loader.load_directory(tmp_path)
    
    assert len(documents) == 2
    doc_ids = [d.metadata.doc_id for d in documents]
    assert "article1" in doc_ids
    assert "notes" in doc_ids
