"""Integration tests for MCPAgent planning loop and model providers."""

import pytest
from mcp_defense_lab.core.agent import MCPAgent
from mcp_defense_lab.core.llm_provider import ScriptedBehaviorMode, ScriptedFakeModelProvider
from mcp_defense_lab.core.models import DecisionOutcome
from mcp_defense_lab.core.simulator import SafeSimulator
from mcp_defense_lab.defenses.baseline import NoDefenseBaseline
from mcp_defense_lab.defenses.intent_alignment import IntentAlignmentDefense
from mcp_defense_lab.evaluation.datasets import generate_synthetic_benchmark


@pytest.fixture
def benchmark_suite():
    return generate_synthetic_benchmark()


def test_agent_vulnerable_baseline_allows_attack(benchmark_suite):
    # Under naive compliant model and no-defense baseline, attack succeeds
    attack_case = next(c for c in benchmark_suite if c.is_attack)
    provider = ScriptedFakeModelProvider(mode=ScriptedBehaviorMode.NAIVE_COMPLIANT)
    defense = NoDefenseBaseline()
    agent = MCPAgent(provider=provider, defense=defense, simulator=SafeSimulator())

    telemetry = agent.run_case(attack_case)
    assert telemetry.proposal.is_valid
    assert telemetry.defense_decision.decision == DecisionOutcome.ALLOW
    assert telemetry.execution.executed
    assert telemetry.execution.attack_succeeded


def test_agent_with_intent_defense_blocks_attack(benchmark_suite):
    # Under naive compliant model and IntentAlignmentDefense, attack is thwarted!
    attack_case = next(c for c in benchmark_suite if c.is_attack)
    provider = ScriptedFakeModelProvider(mode=ScriptedBehaviorMode.NAIVE_COMPLIANT)
    defense = IntentAlignmentDefense()
    agent = MCPAgent(provider=provider, defense=defense, simulator=SafeSimulator())

    telemetry = agent.run_case(attack_case)
    assert telemetry.proposal.is_valid
    assert telemetry.defense_decision.decision == DecisionOutcome.BLOCK
    assert not telemetry.execution.executed
    assert not telemetry.execution.attack_succeeded


def test_agent_benign_task_completion(benchmark_suite):
    benign_case = next(c for c in benchmark_suite if not c.is_attack)
    provider = ScriptedFakeModelProvider(mode=ScriptedBehaviorMode.BENIGN_OPTIMAL)
    defense = IntentAlignmentDefense()
    agent = MCPAgent(provider=provider, defense=defense, simulator=SafeSimulator())

    telemetry = agent.run_case(benign_case)
    assert telemetry.proposal.is_valid
    assert telemetry.defense_decision.decision == DecisionOutcome.ALLOW
    assert telemetry.execution.executed
    assert telemetry.execution.benign_completed


def test_agent_handles_malformed_model_output(benchmark_suite):
    benign_case = benchmark_suite[0]
    provider = ScriptedFakeModelProvider(mode=ScriptedBehaviorMode.MALFORMED_OUTPUT)
    defense = IntentAlignmentDefense()
    agent = MCPAgent(provider=provider, defense=defense, simulator=SafeSimulator())

    telemetry = agent.run_case(benign_case)
    assert not telemetry.proposal.is_valid
    assert telemetry.execution.status == "invalid_proposal"
    assert not telemetry.execution.executed
    assert not telemetry.execution.attack_succeeded
    assert not telemetry.execution.benign_completed
