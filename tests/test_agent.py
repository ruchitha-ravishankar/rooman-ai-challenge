"""Unit and integration tests for Research Agent with Citations."""

import pytest
from app.models.research import ResearchRequest
from app.retrieval.indexer import CorpusIndex
from app.agent.engine import ResearchAgent
from app.agent.llm_provider import LLMProvider


@pytest.fixture(scope="module")
def agent():
    index = CorpusIndex()
    index.build_from_sources()
    llm = LLMProvider()
    return ResearchAgent(index=index, llm=llm)


def test_agent_factual_retrieval_and_citations(agent):
    """Test factual question produces valid citations and grounded verification."""
    req = ResearchRequest(
        query="How does FlashAttention-2 achieve GPU memory speedups on H100 GPUs?",
        top_k=5,
        strict_citations=True
    )
    result = agent.run(req)

    assert not result.is_fallback
    assert len(result.citations) > 0
    assert any("frontier_ai_architectures" in cit.doc_id for cit in result.citations)
    assert result.verification_report is not None
    assert result.verification_report.grounding_score >= 0.70


def test_agent_comparative_synthesis(agent):
    """Test comparative inquiry synthesizes both comparison targets with citations."""
    req = ResearchRequest(
        query="Compare the thermodynamic regeneration temperatures of solid sorbent versus liquid solvent Direct Air Capture.",
        top_k=5,
        strict_citations=True
    )
    result = agent.run(req)

    assert not result.is_fallback
    assert len(result.citations) >= 1
    assert "climate_direct_air_capture" in [c.doc_id for c in result.citations]
    assert result.confidence > 0.60
