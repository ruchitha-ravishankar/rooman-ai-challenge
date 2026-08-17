"""Pydantic schemas for Research Agent query, synthesis, citations, and verification."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.models.document import ScoredChunk


def utc_now():
    return datetime.now(timezone.utc)


class ResearchRequest(BaseModel):
    """Input payload for a research question."""
    query: str = Field(..., min_length=2, description="The research question or topic to investigate")
    top_k: int = Field(5, ge=1, le=20, description="Max source passages to retrieve")
    strict_citations: bool = Field(True, description="Enforce strict claim-level citation grounding")
    doc_filter: Optional[List[str]] = Field(None, description="Optional filter to restrict search to specific doc_ids")


class Citation(BaseModel):
    """Explicit citation linking a claim to its underlying source passage."""
    citation_id: str = Field(..., description="Short marker like [1], [Doc1: Sec 2]")
    doc_id: str = Field(..., description="Referenced document ID")
    chunk_id: str = Field(..., description="Referenced chunk ID")
    document_title: str = Field(..., description="Title of the cited document")
    section: str = Field("General", description="Section header of the passage")
    page_number: Optional[int] = Field(None, description="PDF page number if available")
    quote: str = Field(..., description="Exact verbatim supporting quote from the source passage")
    relevance_score: float = Field(..., description="Retrieval similarity score of the chunk")


class ClaimVerification(BaseModel):
    """Verification analysis for a single generated factual claim."""
    claim_id: int = Field(..., description="1-indexed claim number")
    claim_text: str = Field(..., description="Extracted individual factual claim sentence")
    cited_marker: Optional[str] = Field(None, description="Citation marker attached to claim, e.g. [1]")
    is_grounded: bool = Field(..., description="Whether the claim is strictly supported by source text")
    grounding_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of factual support")
    matched_chunk_id: Optional[str] = Field(None, description="Chunk ID supporting the claim")
    rationale: str = Field(..., description="Verification rationale explaining support or discrepancy")


class VerificationReport(BaseModel):
    """Comprehensive anti-hallucination verification audit for a research answer."""
    total_claims: int = Field(0, description="Total factual claims detected in answer")
    verified_claims: int = Field(0, description="Claims fully supported by source evidence")
    unverified_claims: int = Field(0, description="Claims lacking sufficient evidence or hallucinated")
    grounding_score: float = Field(..., ge=0.0, le=1.0, description="Ratio of verified claims (0.0 - 1.0)")
    is_fully_grounded: bool = Field(..., description="True if grounding_score >= threshold and unverified == 0")
    claim_details: List[ClaimVerification] = Field(default_factory=list)


class ResearchStepLog(BaseModel):
    """Telemetry log for a single agentic reasoning step."""
    step_name: str = Field(..., description="Name of step: Query Analysis, Retrieval, Synthesis, Verification")
    status: str = Field("completed", description="Status: running, completed, skipped, fallback")
    detail: str = Field(..., description="Summary of action taken")
    duration_ms: float = Field(0.0, description="Execution time in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResearchResult(BaseModel):
    """Full research agent response payload with synthesis, citations, and audit trail."""
    query: str = Field(..., description="Original user query")
    answer: str = Field(..., description="Synthesized, citation-grounded research answer (markdown)")
    is_fallback: bool = Field(False, description="True if answer is an unanswerable / insufficient evidence refusal")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall answer confidence score")
    citations: List[Citation] = Field(default_factory=list, description="Unique source citations referenced")
    retrieved_sources: List[ScoredChunk] = Field(default_factory=list, description="Top retrieved context chunks")
    verification_report: Optional[VerificationReport] = Field(None, description="Detailed anti-hallucination audit")
    sub_queries: List[str] = Field(default_factory=list, description="Decomposed search queries used")
    execution_steps: List[ResearchStepLog] = Field(default_factory=list, description="Agent reasoning execution trace")
    total_time_ms: float = Field(0.0, description="Total latency in milliseconds")
    created_at: datetime = Field(default_factory=utc_now)
