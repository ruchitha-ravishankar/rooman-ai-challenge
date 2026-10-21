"""Base interface and schemas for MCP Defense Lab defenses."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from mcp_defense_lab.core.models import (
    DefenseDecision,
    ToolCallProposal,
    ToolSchema,
)


class DefenseStrategy(ABC):
    """Abstract base class for all MCP tool call defenses."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the defense strategy."""
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of how the defense operates."""
        raise NotImplementedError

    @abstractmethod
    def evaluate(
        self,
        user_prompt: str,
        proposal: ToolCallProposal,
        available_tools: list[ToolSchema],
    ) -> DefenseDecision:
        """Evaluate a candidate tool call proposal against safety and alignment policies.

        Must return a structured DefenseDecision with allow, block, or abstain outcome.
        Must fail-closed for any invalid decisions involving side effects.
        """
        raise NotImplementedError
