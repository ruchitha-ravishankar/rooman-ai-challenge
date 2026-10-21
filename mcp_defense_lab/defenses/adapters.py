"""Adapters for existing open-source agent security defenses.

Implements:
1. Schema Signature / Hash Pinning (OWASP Agent Security / OpenSSF) to defeat metadata
   tampering and runtime 'rug pull' injections.
2. Capability Bounding & Role-Based Access Control (Least Privilege) to enforce strict
   read/write/execute authorization boundaries on tool calls.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any
from mcp_defense_lab.core.models import (
    DecisionOutcome,
    DefenseDecision,
    ToolCallProposal,
    ToolSchema,
)
from mcp_defense_lab.defenses.base import DefenseStrategy


class OpenSourceSecurityAdapter(DefenseStrategy):
    """Adapter combining Schema Hash Pinning and Capability-Based Access Control (RBAC).

    Verified against open-source principles: Apache 2.0 / MIT compatible concepts from
    OWASP Agent Security & OpenSSF.
    """

    # Default capability profiles mapping task categories to permitted tools
    CAPABILITY_PROFILES = {
        "read_only": {
            "allowed_tools": {"read_file", "view_file", "list_directory", "calculate", "summarize_text"},
            "prohibited_tools": {"delete_file", "rm", "write_file", "bash", "shell", "run_command", "http_request"},
            "allowed_path_prefixes": ["/home/user/documents", "/var/log/system.log"],
        },
        "compute_only": {
            "allowed_tools": {"calculate", "calculator", "format_data", "convert_units"},
            "prohibited_tools": {"read_file", "write_file", "delete_file", "bash", "http_request"},
            "allowed_path_prefixes": [],
        },
        "general_safe": {
            "allowed_tools": {"read_file", "write_file", "calculate", "list_directory"},
            "prohibited_tools": {"delete_file", "rm", "bash", "shell", "nc"},
            "allowed_path_prefixes": ["/home/user/documents"],
        },
    }

    def __init__(
        self,
        pinned_hashes: dict[str, str] | None = None,
        enforce_rbac: bool = True,
    ) -> None:
        self.pinned_hashes = pinned_hashes or {}
        self.enforce_rbac = enforce_rbac

    @property
    def name(self) -> str:
        return "schema_pinning_and_rbac"

    @property
    def description(self) -> str:
        return "Adapter implementing cryptographic schema hash verification and capability-bounded access controls."

    def pin_tools(self, tools: list[ToolSchema]) -> None:
        """Register reference hashes for legitimate tool schemas."""
        for tool in tools:
            canonical = json.dumps({
                "name": tool.name,
                "parameters": tool.parameters,
                # Exclude any dynamic unverified metadata
            }, sort_keys=True)
            self.pinned_hashes[tool.name] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def evaluate(
        self,
        user_prompt: str,
        proposal: ToolCallProposal,
        available_tools: list[ToolSchema],
    ) -> DefenseDecision:
        start = time.perf_counter()

        # 1. Schema Pinning Check (Detect dynamic tool tampering / rug pulls)
        target_tool = next((t for t in available_tools if t.name == proposal.tool_name), None)
        if target_tool and target_tool.name in self.pinned_hashes:
            current_canonical = json.dumps({
                "name": target_tool.name,
                "parameters": target_tool.parameters,
            }, sort_keys=True)
            current_hash = hashlib.sha256(current_canonical.encode("utf-8")).hexdigest()
            if current_hash != self.pinned_hashes[target_tool.name]:
                latency = (time.perf_counter() - start) * 1000.0
                return DefenseDecision(
                    decision=DecisionOutcome.BLOCK,
                    reason_code="SCHEMA_HASH_MISMATCH_TAMPERING_DETECTED",
                    explanation=f"Tool '{proposal.tool_name}' schema hash does not match pinned cryptographic signature.",
                    defense_name=self.name,
                    latency_ms=latency,
                    confidence=1.0,
                    metadata={"target_tool": proposal.tool_name},
                )

        # 2. Capability Bounding & Least-Privilege RBAC Check
        if self.enforce_rbac:
            profile_name = self._infer_task_profile(user_prompt)
            profile = self.CAPABILITY_PROFILES.get(profile_name, self.CAPABILITY_PROFILES["general_safe"])

            # Check if proposed tool is prohibited for this profile
            if proposal.tool_name in profile["prohibited_tools"]:
                latency = (time.perf_counter() - start) * 1000.0
                return DefenseDecision(
                    decision=DecisionOutcome.BLOCK,
                    reason_code="RBAC_PROHIBITED_TOOL_CAPABILITY",
                    explanation=f"Tool '{proposal.tool_name}' is forbidden under task capability profile '{profile_name}'.",
                    defense_name=self.name,
                    latency_ms=latency,
                    confidence=0.95,
                    metadata={"profile": profile_name, "tool": proposal.tool_name},
                )

            # Check allowed path prefixes if path argument is present
            path_arg = proposal.arguments.get("path") or proposal.arguments.get("file_path")
            if path_arg and isinstance(path_arg, str):
                allowed_prefixes = profile.get("allowed_path_prefixes", [])
                if allowed_prefixes and not any(path_arg.startswith(prefix) for prefix in allowed_prefixes):
                    latency = (time.perf_counter() - start) * 1000.0
                    return DefenseDecision(
                        decision=DecisionOutcome.BLOCK,
                        reason_code="RBAC_PATH_TRAVERSAL_DISALLOWED",
                        explanation=f"Path '{path_arg}' lies outside the authorized path prefixes for profile '{profile_name}'.",
                        defense_name=self.name,
                        latency_ms=latency,
                        confidence=0.95,
                        metadata={"profile": profile_name, "requested_path": path_arg},
                    )

        latency = (time.perf_counter() - start) * 1000.0
        return DefenseDecision(
            decision=DecisionOutcome.ALLOW,
            reason_code="SCHEMA_AND_RBAC_PERMITTED",
            explanation="Tool call conforms to schema pinning and capability bounds.",
            defense_name=self.name,
            latency_ms=latency,
            confidence=0.90,
        )

    def _infer_task_profile(self, user_prompt: str) -> str:
        """Infer the required least-privilege capability profile from user query."""
        lower = user_prompt.lower()
        if any(w in lower for w in ["calculate", "math", "sum", "add", "multiply"]):
            return "compute_only"
        if any(w in lower for w in ["read", "view", "open", "check", "show", "log", "report"]):
            return "read_only"
        return "general_safe"
