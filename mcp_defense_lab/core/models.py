"""Pydantic domain models for MCP Defense Lab."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class AttackParadigm(str, Enum):
    """MCPTox attack paradigms."""
    TEMPLATE_1 = "Template-1"  # Explicit-trigger function hijack
    TEMPLATE_2 = "Template-2"  # Implicit-trigger function hijack
    TEMPLATE_3 = "Template-3"  # Implicit-trigger parameter tampering
    BENIGN = "Benign"          # No attack


class SecurityRiskCategory(str, Enum):
    """Security risk categories from MCPTox / OWASP Agent Security."""
    CREDENTIAL_LEAKAGE = "Credential Leakage"
    PRIVACY_LEAKAGE = "Privacy Leakage"
    INFRASTRUCTURE_DAMAGE = "Infrastructure Damage"
    INFORMATION_MANIPULATION = "Information Manipulation"
    BENIGN = "Benign Task"


class DecisionOutcome(str, Enum):
    """Possible defense outcomes."""
    ALLOW = "allow"
    BLOCK = "block"
    ABSTAIN = "abstain"


class ToolParameter(BaseModel):
    """Specification of a single tool argument."""
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    enum: list[str] | None = None
    default: Any = None


class ToolSchema(BaseModel):
    """MCP tool specification provided to an agent."""
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    server_name: str = "default_mcp_server"
    # Ground-truth research metadata (never presented to LLM prompt)
    is_poisoned: bool = False
    poison_paradigm: AttackParadigm | None = None
    target_risk: SecurityRiskCategory | None = None
    injected_directive: str | None = None

    def to_mcp_json_schema(self) -> dict[str, Any]:
        """Convert to standard MCP tool presentation format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolCallProposal(BaseModel):
    """Candidate tool call proposed by the agent runtime."""
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    raw_response: str = ""
    model_name: str = "unknown"
    model_type: Literal["synthetic_offline", "ollama_local"] = "synthetic_offline"
    proposal_latency_ms: float = 0.0
    is_valid: bool = True
    validation_error: str | None = None


class DefenseDecision(BaseModel):
    """Structured decision emitted by a defense strategy."""
    decision: DecisionOutcome
    reason_code: str
    explanation: str
    defense_name: str
    latency_ms: float = 0.0
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulatedSideEffect(BaseModel):
    """Record of a safe simulated side effect."""
    effect_type: str  # e.g. "FILE_READ", "FILE_WRITE", "COMMAND_EXEC", "NETWORK_CALL"
    target: str       # e.g. "/etc/shadow", "https://attacker.site/exfil"
    details: dict[str, Any] = Field(default_factory=dict)
    is_harmful: bool = False


class ExecutionOutcome(BaseModel):
    """Result of attempting to execute an allowed tool call inside the safe simulator."""
    executed: bool
    was_blocked: bool
    status: Literal["executed", "blocked", "abstain_refused", "invalid_proposal", "simulator_error"]
    output: str = ""
    side_effects: list[SimulatedSideEffect] = Field(default_factory=list)
    attack_succeeded: bool = False
    benign_completed: bool = False
    execution_latency_ms: float = 0.0
    error_message: str | None = None


class BenchmarkCase(BaseModel):
    """A test case containing a user query, available tools, and ground-truth expectations."""
    case_id: str
    title: str
    user_prompt: str
    tools: list[ToolSchema]
    is_attack: bool
    paradigm: AttackParadigm = AttackParadigm.BENIGN
    risk_category: SecurityRiskCategory = SecurityRiskCategory.BENIGN
    expected_benign_tool: str | None = None
    expected_benign_args: dict[str, Any] | None = None
    malicious_target_signature: str | None = None
    description: str = ""


class CaseTelemetry(BaseModel):
    """Complete telemetry record for a single evaluation run of a case."""
    case_id: str
    experiment_id: str
    defense_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    case: BenchmarkCase
    proposal: ToolCallProposal
    defense_decision: DefenseDecision
    execution: ExecutionOutcome
    total_latency_ms: float = 0.0
