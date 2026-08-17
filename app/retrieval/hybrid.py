"""Hybrid Retrieval Engine implementing Reciprocal Rank Fusion (RRF) and Absolute Score Calibration."""

from typing import List, Dict, Optional, Tuple
from app.config import settings
from app.models.document import Chunk, ScoredChunk
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.dense import DenseRetriever


class HybridRetriever:
    """Combines BM25 keyword matching and Dense semantic vector search with calibrated relevance scores."""

    def __init__(
        self,
        bm25: Optional[BM25Retriever] = None,
        dense: Optional[DenseRetriever] = None,
        alpha: float = settings.HYBRID_ALPHA,
        rrf_k: int = settings.RRF_K
    ):
        self.bm25 = bm25 or BM25Retriever()
        self.dense = dense or DenseRetriever()
        self.alpha = alpha  # Weight on dense search (0.0 = pure BM25, 1.0 = pure Dense)
        self.rrf_k = rrf_k  # RRF constant (default 60)
        self.chunks: List[Chunk] = []

    def fit(self, chunks: List[Chunk]) -> None:
        """Indexes chunks across both BM25 and Dense search indices."""
        self.chunks = chunks
        self.bm25.fit(chunks)
        self.dense.fit(chunks)

    def search(
        self,
        query: str,
        top_k: int = settings.TOP_K_CHUNKS,
        doc_filter: Optional[List[str]] = None,
        use_rrf: bool = True
    ) -> List[ScoredChunk]:
        """Performs hybrid retrieval with calibrated absolute similarity scores."""
        if not self.chunks:
            return []

        candidate_k = min(len(self.chunks), max(top_k * 3, 15))

        bm25_results = self.bm25.search(query, top_k=candidate_k, doc_filter=doc_filter)
        dense_results = self.dense.search(query, top_k=candidate_k, doc_filter=doc_filter)

        if not bm25_results and not dense_results:
            return []

        return self._reciprocal_rank_fusion(bm25_results, dense_results, top_k)

    def _reciprocal_rank_fusion(
        self,
        bm25_results: List[Tuple[Chunk, float]],
        dense_results: List[Tuple[Chunk, float]],
        top_k: int
    ) -> List[ScoredChunk]:
        """Calculates Reciprocal Rank Fusion (RRF) scores calibrated by true semantic similarity."""
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Chunk] = {}
        bm25_map: Dict[str, float] = {}
        dense_map: Dict[str, float] = {}

        # Process BM25 ranks
        for rank, (chunk, score) in enumerate(bm25_results, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            bm25_map[cid] = score
            rrf_weight = (1.0 - self.alpha)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (rrf_weight / (self.rrf_k + rank))

        # Process Dense ranks
        for rank, (chunk, score) in enumerate(dense_results, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            dense_map[cid] = score
            rrf_weight = self.alpha
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (rrf_weight / (self.rrf_k + rank))

        # Sort chunks by RRF score descending
        sorted_cids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

        scored_chunks: List[ScoredChunk] = []
        for rank, cid in enumerate(sorted_cids[:top_k], start=1):
            bm25_val = bm25_map.get(cid, 0.0)
            dense_val = dense_map.get(cid, 0.0)

            # Calibrated absolute score
            norm_bm25 = min(1.0, bm25_val / 12.0)
            calibrated_score = (1.0 - self.alpha) * norm_bm25 + self.alpha * dense_val

            scored_chunks.append(ScoredChunk(
                chunk=chunk_map[cid],
                score=round(min(1.0, max(0.0, float(calibrated_score))), 4),
                bm25_score=round(float(bm25_val), 4),
                dense_score=round(float(dense_val), 4),
                rank=rank
            ))

        return scored_chunks
