"""Agent loop for MCP Defense Lab."""

from __future__ import annotations

import time
from typing import Any
from mcp_defense_lab.core.llm_provider import BaseLLMProvider
from mcp_defense_lab.core.models import (
    BenchmarkCase,
    CaseTelemetry,
    DecisionOutcome,
    DefenseDecision,
    ExecutionOutcome,
    ToolCallProposal,
)
from mcp_defense_lab.core.simulator import SafeSimulator
from mcp_defense_lab.defenses.base import DefenseStrategy


class MCPAgent:
    """Agent runtime that receives a user request, reads tool schemas, queries a model,

    evaluates proposals through a defense, and executes allowed calls in the safe simulator.
    """

    def __init__(
        self,
        provider: BaseLLMProvider,
        defense: DefenseStrategy,
        simulator: SafeSimulator | None = None,
    ) -> None:
        self.provider = provider
        self.defense = defense
        self.simulator = simulator or SafeSimulator()

    def run_case(self, case: BenchmarkCase, experiment_id: str = "default_experiment") -> CaseTelemetry:
        """Execute a single benchmark case end-to-end and record complete telemetry."""
        overall_start = time.perf_counter()

        # Step 1: Model proposes a tool call
        proposal: ToolCallProposal = self.provider.propose_tool_call(
            user_prompt=case.user_prompt,
            available_tools=case.tools,
        )

        # Step 2: Validate proposal syntax and schema
        if not proposal.is_valid:
            # If the model produced invalid output, record immediate blocked/invalid outcome
            defense_decision = DefenseDecision(
                decision=DecisionOutcome.BLOCK,
                reason_code="INVALID_PROPOSAL_SYNTAX",
                explanation=proposal.validation_error or "Model proposal was malformed or not found.",
                defense_name=self.defense.name,
                latency_ms=0.0,
                confidence=1.0,
            )
            execution_outcome = ExecutionOutcome(
                executed=False,
                was_blocked=True,
                status="invalid_proposal",
                output=f"Invalid model proposal: {proposal.validation_error}",
                side_effects=[],
                attack_succeeded=False,
                benign_completed=False,
                error_message=proposal.validation_error,
            )
            total_latency = (time.perf_counter() - overall_start) * 1000.0
            return CaseTelemetry(
                case_id=case.case_id,
                experiment_id=experiment_id,
                defense_name=self.defense.name,
                case=case,
                proposal=proposal,
                defense_decision=defense_decision,
                execution=execution_outcome,
                total_latency_ms=total_latency,
            )

        # Step 3: Run proposal through defense strategy
        defense_start = time.perf_counter()
        try:
            defense_decision = self.defense.evaluate(
                user_prompt=case.user_prompt,
                proposal=proposal,
                available_tools=case.tools,
            )
        except Exception as exc:
            # Fail closed on unexpected defense error
            defense_decision = DefenseDecision(
                decision=DecisionOutcome.BLOCK,
                reason_code="DEFENSE_RUNTIME_EXCEPTION_FAIL_CLOSED",
                explanation=f"Defense threw unexpected exception: {exc}. Failing closed.",
                defense_name=self.defense.name,
                latency_ms=(time.perf_counter() - defense_start) * 1000.0,
                confidence=0.0,
            )

        # Step 4: Execute allowed proposals in safe simulator
        execution_outcome = self.simulator.execute(
            case=case,
            proposal=proposal,
            decision=defense_decision,
        )

        total_latency = (time.perf_counter() - overall_start) * 1000.0

        return CaseTelemetry(
            case_id=case.case_id,
            experiment_id=experiment_id,
            defense_name=self.defense.name,
            case=case,
            proposal=proposal,
            defense_decision=defense_decision,
            execution=execution_outcome,
            total_latency_ms=total_latency,
        )
