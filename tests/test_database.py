"""Integration tests for SQLite persistence and repository operations."""

import tempfile
from pathlib import Path
import pytest
from mcp_defense_lab.core.models import (
    AttackParadigm,
    BenchmarkCase,
    CaseTelemetry,
    DecisionOutcome,
    DefenseDecision,
    ExecutionOutcome,
    SecurityRiskCategory,
    ToolCallProposal,
)
from mcp_defense_lab.db.database import DatabaseManager
from mcp_defense_lab.db.repository import ExperimentRepository
from mcp_defense_lab.evaluation.metrics import compute_metrics


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        mgr = DatabaseManager(db_path=db_path)
        yield ExperimentRepository(manager=mgr)


def test_save_and_retrieve_experiment(temp_repo):
    telemetry = [
        CaseTelemetry(
            case_id="c1",
            experiment_id="exp_test",
            defense_name="test_defense",
            case=BenchmarkCase(
                case_id="c1",
                title="Test Case",
                user_prompt="Read something",
                tools=[],
                is_attack=True,
                paradigm=AttackParadigm.TEMPLATE_1,
                risk_category=SecurityRiskCategory.CREDENTIAL_LEAKAGE,
            ),
            proposal=ToolCallProposal(tool_name="read_file", arguments={"path": "notes.txt"}, is_valid=True),
            defense_decision=DefenseDecision(
                decision=DecisionOutcome.BLOCK,
                reason_code="BLOCKED",
                explanation="Denied",
                defense_name="test_defense",
            ),
            execution=ExecutionOutcome(executed=False, was_blocked=True, status="blocked", attack_succeeded=False),
        )
    ]
    report = compute_metrics(telemetry)

    temp_repo.save_experiment(
        experiment_id="exp_test",
        title="Integration Test Experiment",
        defense_name="test_defense",
        model_provider="synthetic_offline",
        model_name="mock-v1",
        config={"seed": 42},
        telemetry_records=telemetry,
        report=report,
    )

    experiments = temp_repo.list_experiments()
    assert len(experiments) == 1
    assert experiments[0]["id"] == "exp_test"
    assert experiments[0]["defense_name"] == "test_defense"

    details = temp_repo.get_experiment_details("exp_test")
    assert details is not None
    assert details["title"] == "Integration Test Experiment"
    assert len(details["cases"]) == 1
    assert details["cases"][0]["case_id"] == "c1"
    assert details["cases"][0]["defense_decision"] == "block"
