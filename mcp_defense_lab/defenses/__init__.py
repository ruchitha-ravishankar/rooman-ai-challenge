"""Defense strategies registry and factory."""

from __future__ import annotations

from typing import Any
from mcp_defense_lab.defenses.adapters import OpenSourceSecurityAdapter
from mcp_defense_lab.defenses.base import DefenseStrategy
from mcp_defense_lab.defenses.baseline import NoDefenseBaseline
from mcp_defense_lab.defenses.intent_alignment import IntentAlignmentDefense
from mcp_defense_lab.defenses.keyword import KeywordRuleScanner
from mcp_defense_lab.defenses.llm_judge import LLMJudgeScanner

DEFENSE_REGISTRY: dict[str, type[DefenseStrategy]] = {
    "no_defense_baseline": NoDefenseBaseline,
    "keyword_rule_scanner": KeywordRuleScanner,
    "llm_judge_scanner": LLMJudgeScanner,
    "schema_pinning_and_rbac": OpenSourceSecurityAdapter,
    "intent_alignment_defense": IntentAlignmentDefense,
}


def get_defense(name: str, **kwargs: Any) -> DefenseStrategy:
    """Instantiate a defense strategy by name."""
    if name not in DEFENSE_REGISTRY:
        raise ValueError(
            f"Unknown defense strategy '{name}'. Available: {list(DEFENSE_REGISTRY.keys())}"
        )
    return DEFENSE_REGISTRY[name](**kwargs)


def list_available_defenses() -> list[dict[str, str]]:
    """Return catalog of available defense strategies and descriptions."""
    results = []
    for key, cls in DEFENSE_REGISTRY.items():
        instance = cls()
        results.append({
            "id": key,
            "name": instance.name,
            "description": instance.description,
        })
    return results


__all__ = [
    "DefenseStrategy",
    "NoDefenseBaseline",
    "KeywordRuleScanner",
    "LLMJudgeScanner",
    "OpenSourceSecurityAdapter",
    "IntentAlignmentDefense",
    "DEFENSE_REGISTRY",
    "get_defense",
    "list_available_defenses",
]
