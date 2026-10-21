"""Unit tests for statistical metric computations and Wilson confidence intervals."""

import pytest
from mcp_defense_lab.core.models import (
    BenchmarkCase,
    CaseTelemetry,
    DecisionOutcome,
    DefenseDecision,
    ExecutionOutcome,
    ToolCallProposal,
)
from mcp_defense_lab.evaluation.metrics import (
    compute_metrics,
    wilson_score_interval,
)


def test_wilson_score_interval_properties():
    # 0 successes out of 20
    ci_0 = wilson_score_interval(0, 20)
    assert ci_0.point_estimate == 0.0
    assert ci_0.ci_lower == 0.0
    assert 0.0 < ci_0.ci_upper <= 0.20

    # 20 successes out of 20
    ci_1 = wilson_score_interval(20, 20)
    assert ci_1.point_estimate == 1.0
    assert 0.80 <= ci_1.ci_lower < 1.0
    assert ci_1.ci_upper == 1.0

    # 10 out of 20 (50%)
    ci_mid = wilson_score_interval(10, 20)
    assert ci_mid.point_estimate == 0.5
    assert ci_mid.ci_lower < 0.5 < ci_mid.ci_upper
    # Symmetric width around 0.5
    assert round(ci_mid.point_estimate - ci_mid.ci_lower, 4) == round(ci_mid.ci_upper - ci_mid.point_estimate, 4)

    # Empty sample size
    ci_empty = wilson_score_interval(0, 0)
    assert ci_empty.point_estimate == 0.0
    assert ci_empty.ci_lower == 0.0
    assert ci_empty.ci_upper == 0.0


def test_metric_denominators_and_formulas():
    # Construct 4 telemetry items:
    # 1 Attack: valid, allowed, attack_succeeded = True
    # 1 Attack: valid, blocked, attack_succeeded = False
    # 1 Attack: INVALID proposal (should not count as successful defense, excluded from ASR denominator)
    # 1 Benign: valid, allowed, benign_completed = True

    t1 = CaseTelemetry(
        case_id="a1",
        experiment_id="exp",
        defense_name="d",
        case=BenchmarkCase(case_id="a1", title="A1", user_prompt="p", tools=[], is_attack=True),
        proposal=ToolCallProposal(tool_name="t1", is_valid=True),
        defense_decision=DefenseDecision(decision=DecisionOutcome.ALLOW, reason_code="A", explanation="e", defense_name="d"),
        execution=ExecutionOutcome(executed=True, was_blocked=False, status="executed", attack_succeeded=True),
    )

    t2 = CaseTelemetry(
        case_id="a2",
        experiment_id="exp",
        defense_name="d",
        case=BenchmarkCase(case_id="a2", title="A2", user_prompt="p", tools=[], is_attack=True),
        proposal=ToolCallProposal(tool_name="t2", is_valid=True),
        defense_decision=DefenseDecision(decision=DecisionOutcome.BLOCK, reason_code="B", explanation="e", defense_name="d"),
        execution=ExecutionOutcome(executed=False, was_blocked=True, status="blocked", attack_succeeded=False),
    )

    t3_invalid = CaseTelemetry(
        case_id="a3",
        experiment_id="exp",
        defense_name="d",
        case=BenchmarkCase(case_id="a3", title="A3", user_prompt="p", tools=[], is_attack=True),
        proposal=ToolCallProposal(tool_name="t3", is_valid=False, validation_error="Syntax error"),
        defense_decision=DefenseDecision(decision=DecisionOutcome.BLOCK, reason_code="INV", explanation="e", defense_name="d"),
        execution=ExecutionOutcome(executed=False, was_blocked=True, status="invalid_proposal", attack_succeeded=False),
    )

    t4_benign = CaseTelemetry(
        case_id="b1",
        experiment_id="exp",
        defense_name="d",
        case=BenchmarkCase(case_id="b1", title="B1", user_prompt="p", tools=[], is_attack=False),
        proposal=ToolCallProposal(tool_name="t4", is_valid=True),
        defense_decision=DefenseDecision(decision=DecisionOutcome.ALLOW, reason_code="A", explanation="e", defense_name="d"),
        execution=ExecutionOutcome(executed=True, was_blocked=False, status="executed", benign_completed=True),
    )

    report = compute_metrics([t1, t2, t3_invalid, t4_benign], baseline_asr=1.0)

    # Valid attack denominator should be 2 (t1 and t2; t3 is invalid and excluded!)
    assert report.attack_success_rate.sample_size == 2
    assert report.attack_success_rate.numerator == 1
    assert report.attack_success_rate.point_estimate == 0.5  # 1/2

    # Benign denominator should be 1
    assert report.benign_completion_rate.sample_size == 1
    assert report.benign_completion_rate.point_estimate == 1.0
    assert report.false_positive_rate.point_estimate == 0.0

    # Invalid proposal rate: 1/4 = 25%
    assert report.invalid_proposal_rate.sample_size == 4
    assert report.invalid_proposal_rate.numerator == 1
    assert report.invalid_proposal_rate.point_estimate == 0.25

    # Relative ASR reduction: (1.0 - 0.5) / 1.0 = 50%
    assert report.relative_asr_reduction == 0.50
