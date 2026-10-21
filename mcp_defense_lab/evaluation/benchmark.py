"""Benchmark evaluation harness orchestrating end-to-end experiment runs."""

from __future__ import annotations

from typing import Any
from mcp_defense_lab.core.agent import MCPAgent
from mcp_defense_lab.core.llm_provider import BaseLLMProvider
from mcp_defense_lab.core.models import BenchmarkCase, CaseTelemetry
from mcp_defense_lab.core.simulator import SafeSimulator
from mcp_defense_lab.defenses.base import DefenseStrategy
from mcp_defense_lab.evaluation.metrics import EvaluationReport, compute_metrics


class BenchmarkRunner:
    """Orchestrates running evaluation suites across defense strategies and model providers."""

    def __init__(
        self,
        provider: BaseLLMProvider,
        defense: DefenseStrategy,
        simulator: SafeSimulator | None = None,
    ) -> None:
        self.provider = provider
        self.defense = defense
        self.simulator = simulator or SafeSimulator()
        self.agent = MCPAgent(
            provider=self.provider,
            defense=self.defense,
            simulator=self.simulator,
        )

    def run_suite(
        self,
        cases: list[BenchmarkCase],
        experiment_id: str = "exp_01",
        baseline_asr: float | None = None,
    ) -> tuple[list[CaseTelemetry], EvaluationReport]:
        """Execute all benchmark cases, collect telemetry, and compute statistical metrics."""
        telemetry_records: list[CaseTelemetry] = []

        for case in cases:
            # Reset simulator between test cases to prevent cross-case side effect pollution
            self.simulator.reset()
            telemetry = self.agent.run_case(case=case, experiment_id=experiment_id)
            telemetry_records.append(telemetry)

        report = compute_metrics(telemetry_records, baseline_asr=baseline_asr)
        return telemetry_records, report
