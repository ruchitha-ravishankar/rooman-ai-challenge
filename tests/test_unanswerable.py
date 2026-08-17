"""Tests verifying strict anti-hallucination fallback on unanswerable and out-of-corpus queries."""

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


def test_unanswerable_scifi_query_refusal(agent):
    """Assert agent refuses to answer out-of-domain sci-fi query without hallucinating."""
    req = ResearchRequest(
        query="What are the latest warp-bubble metric tensors and antimatter injection ratios for the Alcubierre interstellar drive in 2026?",
        top_k=5,
        strict_citations=True
    )
    result = agent.run(req)

    assert result.is_fallback is True
    assert "insufficient evidence" in result.answer.lower()
    assert len(result.citations) == 0


def test_unanswerable_municipal_tax_refusal(agent):
    """Assert agent refuses out-of-corpus municipal tax law query."""
    req = ResearchRequest(
        query="What are the official municipal zoning regulations and property tax rates for residential solar installations in Paris, France?",
        top_k=5,
        strict_citations=True
    )
    result = agent.run(req)

    assert result.is_fallback is True
    assert "insufficient evidence" in result.answer.lower()
    assert len(result.citations) == 0
