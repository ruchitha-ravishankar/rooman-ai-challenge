"""FastAPI route handlers for MCP Defense Lab REST API."""

from __future__ import annotations

import uuid
from typing import Any, Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from mcp_defense_lab.core.llm_provider import (
    OllamaProvider,
    ScriptedBehaviorMode,
    ScriptedFakeModelProvider,
)
from mcp_defense_lab.db.repository import repo
from mcp_defense_lab.defenses import DEFENSE_REGISTRY, get_defense, list_available_defenses
from mcp_defense_lab.evaluation.benchmark import BenchmarkRunner
from mcp_defense_lab.evaluation.datasets import generate_synthetic_benchmark
from mcp_defense_lab.fuzzing.fuzzer import AdaptiveFuzzer
from mcp_defense_lab.fuzzing.mutators import (
    ArgumentPathObfuscator,
    BenignContextWrapperMutator,
    SynonymMutator,
    UnicodeZeroWidthMutator,
)

router = APIRouter()


class RunExperimentRequest(BaseModel):
    """Payload to trigger an evaluation experiment."""
    title: str = Field(default="Automated Benchmark Experiment", min_length=1, max_length=100)
    defense_name: str = Field(default="intent_alignment_defense")
    provider: Literal["scripted", "ollama"] = "scripted"
    model_name: str | None = None
    scripted_mode: Literal["naive_compliant", "benign_optimal", "honest_refusing", "malformed_output"] = "naive_compliant"
    sample_count: int = Field(default=40, ge=2, le=100)
    seed: int = Field(default=42, ge=0)


class RunFuzzRequest(BaseModel):
    """Payload to trigger an adaptive fuzzing evaluation."""
    defense_name: str = Field(default="intent_alignment_defense")
    max_mutations_per_case: int = Field(default=2, ge=1, le=5)
    sample_count: int = Field(default=20, ge=2, le=50)
    seed: int = Field(default=42, ge=0)


@router.get("/health")
def health_check() -> dict[str, Any]:
    """Health check verifying SQLite status, available defenses, and Ollama probe."""
    ollama_provider = OllamaProvider()
    ollama_ready = ollama_provider.is_available()

    return {
        "status": "healthy",
        "service": "mcp-defense-lab",
        "database": "sqlite_ready",
        "ollama_available": ollama_ready,
        "available_defenses": list(DEFENSE_REGISTRY.keys()),
    }


@router.get("/api/defenses")
def get_defenses() -> list[dict[str, str]]:
    """Return catalog of all supported defense strategies."""
    return list_available_defenses()


@router.get("/api/cases")
def get_benchmark_cases(limit: int = Query(default=40, ge=1, le=100)) -> list[dict[str, Any]]:
    """Return catalog of synthetic benchmark test cases."""
    cases = generate_synthetic_benchmark()[:limit]
    return [c.model_dump(exclude={"tools": {"__all__": {"injected_directive"}}}) for c in cases]


@router.get("/api/experiments")
def list_experiments() -> list[dict[str, Any]]:
    """List all saved benchmark experiments with headline metrics."""
    return repo.list_experiments()


@router.get("/api/experiments/{experiment_id}")
def get_experiment(experiment_id: str) -> dict[str, Any]:
    """Retrieve full experiment details, configuration, and case telemetry."""
    res = repo.get_experiment_details(experiment_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return res


@router.get("/api/experiments/{experiment_id}/results")
def get_experiment_results(experiment_id: str) -> dict[str, Any]:
    """Retrieve only the computed statistical summary report for an experiment."""
    res = repo.get_experiment_details(experiment_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return {
        "experiment_id": experiment_id,
        "title": res["title"],
        "defense_name": res["defense_name"],
        "model_name": res["model_name"],
        "report": res.get("report"),
    }


@router.post("/api/experiments")
def create_experiment(payload: RunExperimentRequest) -> dict[str, Any]:
    """Run a new benchmark evaluation experiment and persist results in SQLite."""
    if payload.defense_name not in DEFENSE_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid defense '{payload.defense_name}'. Allowed: {list(DEFENSE_REGISTRY.keys())}",
        )

    # Instantiate model provider
    if payload.provider == "ollama":
        provider = OllamaProvider(model_name=payload.model_name)
        if not provider.is_available():
            raise HTTPException(
                status_code=503,
                detail="Local Ollama daemon is unreachable at configured host. Check if ollama is running or use provider='scripted'.",
            )
    else:
        mode_enum = ScriptedBehaviorMode(payload.scripted_mode)
        provider = ScriptedFakeModelProvider(
            mode=mode_enum,
            model_name=payload.model_name or f"scripted-{payload.scripted_mode}",
        )

    # Instantiate defense
    defense = get_defense(payload.defense_name)

    # Prepare cases
    all_cases = generate_synthetic_benchmark()
    selected_cases = all_cases[:payload.sample_count]

    experiment_id = f"exp_{uuid.uuid4().hex[:10]}"
    runner = BenchmarkRunner(provider=provider, defense=defense)

    telemetry, report = runner.run_suite(selected_cases, experiment_id=experiment_id)

    # Persist in database
    repo.save_experiment(
        experiment_id=experiment_id,
        title=payload.title,
        defense_name=payload.defense_name,
        model_provider=provider.model_type,
        model_name=provider.model_name,
        config=payload.model_dump(),
        telemetry_records=telemetry,
        report=report,
    )

    return {
        "message": "Experiment completed and persisted.",
        "experiment_id": experiment_id,
        "total_cases": len(selected_cases),
        "attack_success_rate": report.attack_success_rate.point_estimate,
        "benign_completion_rate": report.benign_completion_rate.point_estimate,
        "false_positive_rate": report.false_positive_rate.point_estimate,
        "defense_block_rate": report.defense_block_rate.point_estimate,
        "median_latency_ms": report.median_total_latency_ms,
    }


@router.get("/api/fuzz-runs")
def list_fuzz_runs() -> list[dict[str, Any]]:
    """List all recorded adaptive fuzzing runs."""
    return repo.list_fuzz_runs()


@router.get("/api/fuzz-runs/{fuzz_run_id}")
def get_fuzz_run(fuzz_run_id: str) -> dict[str, Any]:
    """Retrieve details of an adaptive fuzz run."""
    run = repo.get_fuzz_run(fuzz_run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Fuzz run '{fuzz_run_id}' not found.")
    return run


@router.post("/api/fuzz-runs")
def create_fuzz_run(payload: RunFuzzRequest) -> dict[str, Any]:
    """Execute a bounded adaptive fuzzing run against a defense and calculate evasion degradation."""
    if payload.defense_name not in DEFENSE_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Invalid defense '{payload.defense_name}'.")

    defense = get_defense(payload.defense_name)
    provider = ScriptedFakeModelProvider(mode=ScriptedBehaviorMode.NAIVE_COMPLIANT)

    all_cases = generate_synthetic_benchmark()
    selected_cases = all_cases[:payload.sample_count]

    fuzzer = AdaptiveFuzzer(
        mutators=[
            SynonymMutator(),
            UnicodeZeroWidthMutator(),
            BenignContextWrapperMutator(),
            ArgumentPathObfuscator(),
        ],
        seed=payload.seed,
        max_mutations_per_case=payload.max_mutations_per_case,
    )

    fuzz_id = f"fuzz_{uuid.uuid4().hex[:10]}"
    result = fuzzer.run_fuzz_evaluation(
        defense=defense,
        provider=provider,
        baseline_cases=selected_cases,
        fuzz_run_id=fuzz_id,
    )

    repo.save_fuzz_run(result)

    return {
        "message": "Fuzzing run completed successfully.",
        "fuzz_run_id": fuzz_id,
        "defense_name": payload.defense_name,
        "pre_asr": result.pre_fuzz_report.attack_success_rate.point_estimate,
        "post_asr": result.post_fuzz_report.attack_success_rate.point_estimate,
        "delta_asr": result.delta_asr,
        "delta_tcr": result.delta_tcr,
        "delta_fpr": result.delta_fpr,
        "evasion_summary": result.evasion_summary,
    }
