"""Central Research Agent Orchestrator tying together Analysis, Hybrid Retrieval, Synthesis, and Verification."""

import time
import re
from typing import List, Dict, Optional, Set
from app.config import settings
from app.models.document import ScoredChunk, Chunk
from app.models.research import (
    ResearchRequest,
    ResearchResult,
    Citation,
    ResearchStepLog,
    VerificationReport
)
from app.retrieval.indexer import CorpusIndex
from app.agent.llm_provider import LLMProvider
from app.agent.query_analyzer import QueryAnalyzer
from app.agent.synthesizer import Synthesizer
from app.agent.verifier import ClaimVerifier


class ResearchAgent:
    """End-to-end agent for citation-grounded research synthesis."""

    def __init__(
        self,
        index: CorpusIndex,
        llm: Optional[LLMProvider] = None,
        analyzer: Optional[QueryAnalyzer] = None,
        synthesizer: Optional[Synthesizer] = None,
        verifier: Optional[ClaimVerifier] = None
    ):
        self.index = index
        self.llm = llm or LLMProvider()
        self.analyzer = analyzer or QueryAnalyzer(llm=self.llm)
        self.synthesizer = synthesizer or Synthesizer(llm=self.llm)
        self.verifier = verifier or ClaimVerifier()

    def run(self, request: ResearchRequest) -> ResearchResult:
        """Executes full multi-step research pipeline."""
        start_time = time.time()
        step_logs: List[ResearchStepLog] = []

        # -------------------------------------------------------------
        # STEP 1: Query Analysis & Sub-query Decomposition
        # -------------------------------------------------------------
        step_start = time.time()
        analysis = self.analyzer.analyze(request.query)
        sub_queries = analysis["sub_queries"]
        step_logs.append(ResearchStepLog(
            step_name="Query Decomposition",
            status="completed",
            detail=f"Decomposed query into {len(sub_queries)} search angle(s) (Intent: {analysis['intent']})",
            duration_ms=round((time.time() - step_start) * 1000, 2),
            metadata={"sub_queries": sub_queries, "intent": analysis["intent"]}
        ))

        # -------------------------------------------------------------
        # STEP 2: Multi-Passage Hybrid Retrieval
        # -------------------------------------------------------------
        step_start = time.time()
        retrieved_chunks = self._multi_query_retrieval(
            sub_queries=sub_queries,
            top_k=request.top_k,
            doc_filter=request.doc_filter
        )
        
        step_logs.append(ResearchStepLog(
            step_name="Hybrid Retrieval",
            status="completed",
            detail=f"Retrieved {len(retrieved_chunks)} highest-scoring passages across indexed corpus",
            duration_ms=round((time.time() - step_start) * 1000, 2),
            metadata={"retrieved_count": len(retrieved_chunks)}
        ))

        # -------------------------------------------------------------
        # STEP 3: Relevance Check & Out-of-Corpus Fallback Guard
        # -------------------------------------------------------------
        step_start = time.time()
        max_score = max([sc.score for sc in retrieved_chunks]) if retrieved_chunks else 0.0
        is_low_relevance = max_score < settings.MIN_RELEVANCE_THRESHOLD or not retrieved_chunks

        if is_low_relevance:
            step_logs.append(ResearchStepLog(
                step_name="Relevance Assessment",
                status="fallback",
                detail=f"Max retrieval similarity ({max_score:.3f}) below threshold ({settings.MIN_RELEVANCE_THRESHOLD:.3f}). Triggering unanswerable fallback.",
                duration_ms=round((time.time() - step_start) * 1000, 2),
                metadata={"max_score": max_score, "threshold": settings.MIN_RELEVANCE_THRESHOLD}
            ))

            fallback_answer = (
                "### Insufficient Evidence\n\n"
                f"Based on the provided source documents, there is **insufficient evidence** to answer: *\"{request.query}\"*.\n\n"
                "The indexed repository does not contain relevant passages or factual data addressing this inquiry. "
                "To answer this question, please upload relevant source documents or broaden your query."
            )

            total_ms = round((time.time() - start_time) * 1000, 2)
            return ResearchResult(
                query=request.query,
                answer=fallback_answer,
                is_fallback=True,
                confidence=0.0,
                citations=[],
                retrieved_sources=retrieved_chunks,
                verification_report=VerificationReport(
                    total_claims=0,
                    verified_claims=0,
                    unverified_claims=0,
                    grounding_score=1.0,
                    is_fully_grounded=True,
                    claim_details=[]
                ),
                sub_queries=sub_queries,
                execution_steps=step_logs,
                total_time_ms=total_ms
            )

        step_logs.append(ResearchStepLog(
            step_name="Relevance Assessment",
            status="completed",
            detail=f"Context relevance verified (Top score: {max_score:.3f} >= {settings.MIN_RELEVANCE_THRESHOLD:.3f})",
            duration_ms=round((time.time() - step_start) * 1000, 2),
            metadata={"max_score": max_score}
        ))

        # -------------------------------------------------------------
        # STEP 4: Citation-Grounded Synthesis
        # -------------------------------------------------------------
        step_start = time.time()
        synthesis = self.synthesizer.synthesize(
            query=request.query,
            context_chunks=retrieved_chunks,
            strict_citations=request.strict_citations
        )
        step_logs.append(ResearchStepLog(
            step_name="Grounded Synthesis",
            status="completed",
            detail="Generated structured synthesis with explicit chunk citation anchors",
            duration_ms=round((time.time() - step_start) * 1000, 2)
        ))

        # -------------------------------------------------------------
        # STEP 5: Anti-Hallucination & Claim Verification
        # -------------------------------------------------------------
        step_start = time.time()
        verification_report = self.verifier.verify_answer(
            answer_text=synthesis,
            retrieved_chunks=retrieved_chunks
        )
        step_logs.append(ResearchStepLog(
            step_name="Claim Verification",
            status="completed" if verification_report.is_fully_grounded else "warning",
            detail=f"Audited {verification_report.total_claims} claims: {verification_report.verified_claims} verified ({verification_report.grounding_score * 100:.1f}% Grounding Score)",
            duration_ms=round((time.time() - step_start) * 1000, 2),
            metadata={
                "grounding_score": verification_report.grounding_score,
                "verified": verification_report.verified_claims,
                "unverified": verification_report.unverified_claims
            }
        ))

        # -------------------------------------------------------------
        # STEP 6: Citation Extraction & Resolution
        # -------------------------------------------------------------
        citations = self._build_citation_list(synthesis, retrieved_chunks)

        total_ms = round((time.time() - start_time) * 1000, 2)
        overall_confidence = round(
            0.6 * verification_report.grounding_score + 0.4 * min(1.0, max_score * 1.2),
            4
        )

        return ResearchResult(
            query=request.query,
            answer=synthesis,
            is_fallback=False,
            confidence=overall_confidence,
            citations=citations,
            retrieved_sources=retrieved_chunks,
            verification_report=verification_report,
            sub_queries=sub_queries,
            execution_steps=step_logs,
            total_time_ms=total_ms
        )

    def _multi_query_retrieval(
        self,
        sub_queries: List[str],
        top_k: int,
        doc_filter: Optional[List[str]]
    ) -> List[ScoredChunk]:
        """Runs hybrid search across all sub-queries and merges results without duplicates."""
        chunk_scores: Dict[str, ScoredChunk] = {}

        for query in sub_queries:
            results = self.index.search(query, top_k=top_k, doc_filter=doc_filter)
            for sc in results:
                cid = sc.chunk.chunk_id
                if cid not in chunk_scores or sc.score > chunk_scores[cid].score:
                    chunk_scores[cid] = sc

        # Sort merged candidates by score descending
        merged = sorted(chunk_scores.values(), key=lambda x: x.score, reverse=True)
        
        # Assign unified final ranks
        final_list: List[ScoredChunk] = []
        for idx, sc in enumerate(merged[:top_k], start=1):
            sc.rank = idx
            final_list.append(sc)

        return final_list

    def _build_citation_list(
        self,
        answer_text: str,
        retrieved_chunks: List[ScoredChunk]
    ) -> List[Citation]:
        """Resolves referenced [^CHUNK_ID] markers into rich structured Citation objects."""
        found_cids = set(re.findall(r'\[\^([a-zA-Z0-9_#-]+)\]', answer_text))
        chunk_map = {sc.chunk.chunk_id: sc for sc in retrieved_chunks}

        citations: List[Citation] = []
        for cid in sorted(found_cids):
            if cid in chunk_map:
                sc = chunk_map[cid]
                c = sc.chunk
                
                # Extract first substantive sentence as excerpt quote
                quote_candidates = [s.strip() for s in c.text.split(".") if len(s.strip()) > 20]
                quote = quote_candidates[0] + "." if quote_candidates else c.text[:150] + "..."

                citations.append(Citation(
                    citation_id=f"[^{cid}]",
                    doc_id=c.doc_id,
                    chunk_id=c.chunk_id,
                    document_title=c.title,
                    section=c.section,
                    page_number=c.page_number,
                    quote=quote,
                    relevance_score=sc.score
                ))

        return citations
