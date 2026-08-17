"""Unit tests for Sparse BM25, Dense Vector, and Hybrid RRF Retrieval."""

import pytest
from app.models.document import Chunk
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.dense import DenseRetriever
from app.retrieval.hybrid import HybridRetriever


@pytest.fixture
def sample_chunks():
    return [
        Chunk(
            chunk_id="doc1#c001",
            doc_id="doc1",
            title="Quantum Error Correction",
            section="Surface Codes",
            chunk_index=0,
            text="Surface code error correction arranges physical qubits in a two-dimensional square lattice."
        ),
        Chunk(
            chunk_id="doc2#c001",
            doc_id="doc2",
            title="Direct Air Capture",
            section="Basalt Mineralization",
            chunk_index=0,
            text="Captured carbon dioxide is dissolved in pressurized water and injected into basaltic rock formations."
        ),
        Chunk(
            chunk_id="doc3#c001",
            doc_id="doc3",
            title="Frontier AI",
            section="FlashAttention",
            chunk_index=0,
            text="FlashAttention-2 achieves a 2.3x speedup over FlashAttention-1 by tiling GPU SRAM shared memory."
        )
    ]


def test_bm25_search_precision(sample_chunks):
    """Test BM25 keyword matching returns highest score for target document."""
    bm25 = BM25Retriever()
    bm25.fit(sample_chunks)
    
    results = bm25.search("FlashAttention GPU SRAM speedup", top_k=1)
    assert len(results) == 1
    assert results[0][0].chunk_id == "doc3#c001"
    assert results[0][1] > 0.0


def test_dense_search_semantic_matching(sample_chunks):
    """Test dense vector search finds relevant chunk using semantic query."""
    dense = DenseRetriever()
    dense.fit(sample_chunks)
    
    results = dense.search("carbon removal and rock storage", top_k=1)
    assert len(results) == 1
    assert results[0][0].chunk_id == "doc2#c001"
    assert results[0][1] > 0.0


def test_hybrid_rrf_retrieval(sample_chunks):
    """Test hybrid retrieval combines signals and assigns calibrated scores."""
    hybrid = HybridRetriever()
    hybrid.fit(sample_chunks)
    
    results = hybrid.search("surface code physical qubits", top_k=2)
    assert len(results) >= 1
    assert results[0].chunk.chunk_id == "doc1#c001"
    assert results[0].score > 0.20
    assert results[0].rank == 1
