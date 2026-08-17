"""FastAPI REST API Routes for VeriCite Research Agent."""

import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from app.config import settings, DATA_DIR, SOURCES_DIR
from app.models.document import Document
from app.models.research import ResearchRequest, ResearchResult
from app.models.benchmark import BenchmarkSummaryReport, TestCaseEvaluation, BenchmarkQuestion
from app.retrieval.indexer import CorpusIndex
from app.agent.engine import ResearchAgent
from app.agent.llm_provider import LLMProvider

router = APIRouter(prefix="/api")

# Singleton references initialized on server startup
_corpus_index: Optional[CorpusIndex] = None
_research_agent: Optional[ResearchAgent] = None


def get_index() -> CorpusIndex:
    global _corpus_index
    if _corpus_index is None:
        _corpus_index = CorpusIndex()
        _corpus_index.build_from_sources()
    return _corpus_index


def get_agent(index: CorpusIndex = Depends(get_index)) -> ResearchAgent:
    global _research_agent
    if _research_agent is None or _research_agent.index != index:
        llm = LLMProvider()
        _research_agent = ResearchAgent(index=index, llm=llm)
    return _research_agent


@router.get("/health")
def health_check(index: CorpusIndex = Depends(get_index), agent: ResearchAgent = Depends(get_agent)):
    """Health check and runtime configuration info."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "llm_provider": agent.llm.provider,
        "model_name": agent.llm.model_name,
        "indexed_documents": len(index.documents),
        "indexed_chunks": len(index.chunks)
    }


@router.post("/research", response_model=ResearchResult)
def execute_research(request: ResearchRequest, agent: ResearchAgent = Depends(get_agent)):
    """Executes full research agent workflow with strict citation grounding."""
    try:
        result = agent.run(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research agent execution failed: {str(e)}")


@router.get("/documents")
def list_documents(index: CorpusIndex = Depends(get_index)):
    """Lists summary of all indexed source documents."""
    return {
        "total": len(index.documents),
        "total_chunks": len(index.chunks),
        "documents": index.list_documents()
    }


@router.get("/documents/{doc_id}")
def get_document_details(doc_id: str, index: CorpusIndex = Depends(get_index)):
    """Retrieves full document text and chunk breakdown by doc_id."""
    doc = index.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    return doc


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    index: CorpusIndex = Depends(get_index)
):
    """Uploads a new document (PDF, MD, TXT) and indexes it into the corpus."""
    allowed_extensions = {".pdf", ".md", ".txt", ".json"}
    file_path = SOURCES_DIR / file.filename
    ext = file_path.suffix.lower()
    
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {allowed_extensions}"
        )

    try:
        content = await file.read()
        file_path.write_bytes(content)
        
        doc = index.loader.load_file(file_path)
        if title:
            doc.metadata.title = title
            for c in doc.chunks:
                c.title = title

        total_chunks = index.add_document(doc)
        return {
            "status": "success",
            "message": f"Successfully indexed '{doc.metadata.title}'",
            "doc_id": doc.metadata.doc_id,
            "chunks_added": len(doc.chunks),
            "total_corpus_chunks": total_chunks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@router.get("/benchmark/questions")
def get_benchmark_questions():
    """Returns the benchmark question suite."""
    q_path = DATA_DIR / "questions.json"
    if not q_path.exists():
        raise HTTPException(status_code=404, detail="Benchmark questions file not found")
    return json.loads(q_path.read_text(encoding="utf-8"))


@router.post("/benchmark/run", response_model=BenchmarkSummaryReport)
def run_benchmark_suite(agent: ResearchAgent = Depends(get_agent)):
    """Executes the full 10-question evaluation benchmark suite and returns comprehensive metrics."""
    q_path = DATA_DIR / "questions.json"
    if not q_path.exists():
        raise HTTPException(status_code=404, detail="Benchmark questions file not found")

    cases_data = json.loads(q_path.read_text(encoding="utf-8"))
    evaluations: List[TestCaseEvaluation] = []
    
    total_latency = 0.0
    total_grounding = 0.0
    total_citation_validity = 0.0
    unanswerable_total = 0
    unanswerable_correct = 0
    passed_count = 0

    category_stats: Dict[str, Dict[str, Any]] = {}

    for c in cases_data:
        q_id = c["id"]
        cat = c["category"]
        question = c["question"]
        expected_docs = c.get("expected_doc_ids", [])
        expected_facts = c.get("expected_key_facts", [])
        should_fallback = c.get("should_fallback", False)

        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "passed": 0}
        category_stats[cat]["total"] += 1

        # Run agent
        req = ResearchRequest(query=question, top_k=5, strict_citations=True)
        res = agent.run(req)

        # Evaluate Fallback Correctness
        fallback_ok = (res.is_fallback == should_fallback)
        if should_fallback:
            unanswerable_total += 1
            if res.is_fallback:
                unanswerable_correct += 1

        # Evaluate Citation Validity
        if res.citations:
            valid_cits = [cit for cit in res.citations if not expected_docs or cit.doc_id in expected_docs]
            cit_validity = len(valid_cits) / len(res.citations)
        else:
            cit_validity = 1.0 if should_fallback else 0.0

        # Evaluate Key Facts Coverage
        facts_found = 0
        ans_lower = res.answer.lower()
        if expected_facts:
            for fact in expected_facts:
                if fact.lower() in ans_lower:
                    facts_found += 1
            facts_cov = facts_found / len(expected_facts)
        else:
            facts_cov = 1.0 if should_fallback else 0.0

        grounding_score = res.verification_report.grounding_score if res.verification_report else 1.0

        # Pass condition:
        # If should_fallback: must have triggered fallback
        # If normal query: fallback must be false, grounding >= 0.50, and key facts coverage >= 0.30
        if should_fallback:
            passed = fallback_ok
        else:
            passed = (not res.is_fallback) and (grounding_score >= 0.50) and (facts_cov >= 0.30)

        if passed:
            passed_count += 1
            category_stats[cat]["passed"] += 1

        total_latency += res.total_time_ms
        total_grounding += grounding_score
        total_citation_validity += cit_validity

        notes = []
        if should_fallback and res.is_fallback:
            notes.append("Correctly recognized out-of-corpus query and triggered safe fallback.")
        elif not should_fallback and res.citations:
            notes.append(f"Successfully cited {len(res.citations)} distinct source passage(s).")

        evaluations.append(TestCaseEvaluation(
            question_id=q_id,
            category=cat,
            question=question,
            result=res,
            passed=passed,
            citation_validity=round(cit_validity, 3),
            key_facts_coverage=round(facts_cov, 3),
            fallback_correctness=fallback_ok,
            grounding_score=round(grounding_score, 3),
            latency_ms=res.total_time_ms,
            notes=notes
        ))

    n = len(cases_data)
    pass_rate = round(passed_count / max(1, n), 4)
    avg_latency = round(total_latency / max(1, n), 2)
    avg_grounding = round(total_grounding / max(1, n), 4)
    avg_cit_validity = round(total_citation_validity / max(1, n), 4)
    unanswerable_rate = round(unanswerable_correct / max(1, unanswerable_total), 4) if unanswerable_total else 1.0

    return BenchmarkSummaryReport(
        total_cases=n,
        passed_cases=passed_count,
        pass_rate=pass_rate,
        avg_latency_ms=avg_latency,
        avg_grounding_score=avg_grounding,
        avg_citation_validity=avg_cit_validity,
        unanswerable_detection_rate=unanswerable_rate,
        category_breakdown=category_stats,
        evaluations=evaluations
    )
