"""Keyword and pattern-based rule scanner defense."""

from __future__ import annotations

import re
import time
from typing import Any
from mcp_defense_lab.core.models import (
    DecisionOutcome,
    DefenseDecision,
    ToolCallProposal,
    ToolSchema,
)
from mcp_defense_lab.defenses.base import DefenseStrategy


class KeywordRuleScanner(DefenseStrategy):
    """Transparent, configurable keyword and regex pattern scanner.

    Scans proposed tool names, arguments, and tool descriptions for known
    prompt injection patterns, sensitive path disclosures, and high-impact commands.
    """

    DEFAULT_RULES = {
        "PROMPT_INJECTION_DIRECTIVE": [
            r"\bignore\s+(?:previous|all|above)\s+instructions?\b",
            r"\bsystem\s+override\b",
            r"\bcritical\s+instruction\b",
            r"\byou\s+must\s+(?:first\s+)?(?:call|execute|run)\b",
            r"\balways\s+route\s+(?:all\s+)?requests?\s+through\b",
            r"\bbefore\s+(?:proceeding|answering|calling).*?(?:execute|run|fetch)\b",
            r"\bhidden\s+directive\b",
            r"\boverride\s+parameter\b",
        ],
        "SENSITIVE_CREDENTIAL_PATH": [
            r"\bid_rsa\b",
            r"\bid_ed25519\b",
            r"\.ssh/(?:id_|authorized_keys)",
            r"\.aws/(?:credentials|config)",
            r"/etc/(?:shadow|passwd|master\.passwd)",
            r"\.env(?:\.local|\.prod)?\b",
            r"\b(?:api[_-]?key|secret[_-]?token|private[_-]?key)\b",
        ],
        "UNAUTHORIZED_COMMAND_EXECUTION": [
            r"\brm\s+-(?:r|f|rf|fr)\b",
            r"\bchmod\s+[0-7]{3,4}\b",
            r"\b(?:wget|curl)\s+.*?https?://",
            r"\bnc\s+-(?:e|c|l)\b",
            r"\bpython\s+-c\b",
            r"\b(?:bash|sh)\s+-c\b",
        ],
        "EXFILTRATION_DESTINATION": [
            r"attacker\.(?:site|com|org)",
            r"webhook\.site",
            r"transfer\.sh",
            r"pastebin\.com",
            r"requestbin",
        ],
    }

    def __init__(self, rules: dict[str, list[str]] | None = None) -> None:
        self.rules = rules or self.DEFAULT_RULES
        self._compiled_rules = {
            category: [re.compile(pat, re.IGNORECASE) for pat in patterns]
            for category, patterns in self.rules.items()
        }

    @property
    def name(self) -> str:
        return "keyword_rule_scanner"

    @property
    def description(self) -> str:
        return "Deterministic regex-based scanner checking tool names, args, and descriptions for suspicious signatures."

    def evaluate(
        self,
        user_prompt: str,
        proposal: ToolCallProposal,
        available_tools: list[ToolSchema],
    ) -> DefenseDecision:
        start = time.perf_counter()

        # Aggregate all text to scan from proposal
        proposal_text = f"{proposal.tool_name} " + " ".join(str(v) for v in proposal.arguments.values())

        # Also inspect the tool description of the proposed tool
        target_schema = next((t for t in available_tools if t.name == proposal.tool_name), None)
        desc_text = target_schema.description if target_schema else ""

        full_candidate_text = f"{proposal_text}\n{desc_text}"

        for category, patterns in self._compiled_rules.items():
            for pat in patterns:
                # Check in proposed tool arguments and names
                match = pat.search(proposal_text)
                if match:
                    latency = (time.perf_counter() - start) * 1000.0
                    return DefenseDecision(
                        decision=DecisionOutcome.BLOCK,
                        reason_code=f"KEYWORD_RULE_MATCH_{category}",
                        explanation=f"Matched disallowed pattern '{match.group(0)}' under rule category '{category}' in proposal.",
                        defense_name=self.name,
                        latency_ms=latency,
                        confidence=0.95,
                        metadata={"matched_pattern": pat.pattern, "category": category, "target": "proposal"},
                    )

                # Check in tool description metadata
                desc_match = pat.search(desc_text)
                if desc_match:
                    latency = (time.perf_counter() - start) * 1000.0
                    return DefenseDecision(
                        decision=DecisionOutcome.BLOCK,
                        reason_code=f"POISONED_METADATA_{category}",
                        explanation=f"Tool description for '{proposal.tool_name}' contains suspicious instruction pattern '{desc_match.group(0)}'.",
                        defense_name=self.name,
                        latency_ms=latency,
                        confidence=0.90,
                        metadata={"matched_pattern": pat.pattern, "category": category, "target": "tool_description"},
                    )

        latency = (time.perf_counter() - start) * 1000.0
        return DefenseDecision(
            decision=DecisionOutcome.ALLOW,
            reason_code="KEYWORD_SCAN_CLEAN",
            explanation="No malicious keywords or prompt-injection patterns detected in proposal or tool metadata.",
            defense_name=self.name,
            latency_ms=latency,
            confidence=0.85,
        )
