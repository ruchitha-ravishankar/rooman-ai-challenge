"""No-defense baseline strategy."""

from __future__ import annotations

import time
from mcp_defense_lab.core.models import (
    DecisionOutcome,
    DefenseDecision,
    ToolCallProposal,
    ToolSchema,
)
from mcp_defense_lab.defenses.base import DefenseStrategy


class NoDefenseBaseline(DefenseStrategy):
    """No-defense baseline for comparative security evaluation.

    Allows all proposals through to the simulator without filtering.
    Simulator safety restrictions remain always active.
    """

    @property
    def name(self) -> str:
        return "no_defense_baseline"

    @property
    def description(self) -> str:
        return "Baseline audit-only control strategy that performs no filtering."

    def evaluate(
        self,
        user_prompt: str,
        proposal: ToolCallProposal,
        available_tools: list[ToolSchema],
    ) -> DefenseDecision:
        start = time.perf_counter()
        latency = (time.perf_counter() - start) * 1000.0

        return DefenseDecision(
            decision=DecisionOutcome.ALLOW,
            reason_code="BASELINE_NO_OP",
            explanation="Baseline strategy: proposal allowed without inspection.",
            defense_name=self.name,
            latency_ms=latency,
            confidence=1.0,
        )
