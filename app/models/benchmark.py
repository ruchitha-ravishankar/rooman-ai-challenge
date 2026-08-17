"""Pydantic schemas for Benchmark Evaluation Suite."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.models.research import ResearchResult


def utc_now():
    return datetime.now(timezone.utc)


class BenchmarkQuestion(BaseModel):
    """A benchmark test query specification."""
    id: str = Field(..., description="Unique question identifier, e.g. Q01")
    category: str = Field(..., description="Category: factual, multi_doc_synthesis, comparative, unanswerable")
    question: str = Field(..., description="The query string")
    expected_doc_ids: List[str] = Field(default_factory=list, description="Documents expected to be cited")
    expected_key_facts: List[str] = Field(default_factory=list, description="Key factual phrases that must appear")
    should_fallback: bool = Field(False, description="True if this query is unanswerable from corpus")
    description: str = Field("", description="Why this test case matters")


class TestCaseEvaluation(BaseModel):
    """Evaluation metrics for a single benchmark test query."""
    question_id: str
    category: str
    question: str
    result: ResearchResult
    passed: bool = Field(..., description="Did the test case pass all assertions?")
    citation_validity: float = Field(..., ge=0.0, le=1.0, description="Ratio of valid citations to sources")
    key_facts_coverage: float = Field(..., ge=0.0, le=1.0, description="Ratio of expected facts found in synthesis")
    fallback_correctness: bool = Field(..., description="Whether fallback triggered correctly when expected")
    grounding_score: float = Field(..., ge=0.0, le=1.0, description="Verification grounding score")
    latency_ms: float = Field(0.0)
    notes: List[str] = Field(default_factory=list)


class BenchmarkSummaryReport(BaseModel):
    """Aggregated benchmark report across all test cases."""
    total_cases: int
    passed_cases: int
    pass_rate: float
    avg_latency_ms: float
    avg_grounding_score: float
    avg_citation_validity: float
    unanswerable_detection_rate: float
    category_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    evaluations: List[TestCaseEvaluation] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=utc_now)
