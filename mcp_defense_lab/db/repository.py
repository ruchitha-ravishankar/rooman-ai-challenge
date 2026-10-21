"""Repository functions for persisting and querying experiments, telemetry, and fuzz runs."""

from __future__ import annotations

import json
from typing import Any
from mcp_defense_lab.core.models import CaseTelemetry
from mcp_defense_lab.db.database import DatabaseManager, db
from mcp_defense_lab.evaluation.metrics import EvaluationReport
from mcp_defense_lab.fuzzing.fuzzer import FuzzRunResult


class ExperimentRepository:
    """CRUD operations for evaluation experiments and fuzz runs."""

    def __init__(self, manager: DatabaseManager = db) -> None:
        self.db = manager

    def save_experiment(
        self,
        experiment_id: str,
        title: str,
        defense_name: str,
        model_provider: str,
        model_name: str,
        config: dict[str, Any],
        telemetry_records: list[CaseTelemetry],
        report: EvaluationReport,
    ) -> None:
        """Atomically persist experiment metadata, individual case records, and summary metrics."""
        with self.db.get_connection() as conn:
            # 1. Insert experiment
            conn.execute(
                """
                INSERT OR REPLACE INTO experiments
                (id, title, defense_name, model_provider, model_name, total_cases, config_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    title,
                    defense_name,
                    model_provider,
                    model_name,
                    len(telemetry_records),
                    json.dumps(config),
                ),
            )

            # 2. Insert case records
            conn.execute("DELETE FROM case_records WHERE experiment_id = ?", (experiment_id,))
            for rec in telemetry_records:
                conn.execute(
                    """
                    INSERT INTO case_records
                    (experiment_id, case_id, title, user_prompt, is_attack, paradigm, risk_category,
                     proposal_tool, proposal_args_json, proposal_valid, proposal_latency_ms,
                     defense_decision, defense_reason_code, defense_explanation, defense_latency_ms,
                     executed, attack_succeeded, benign_completed, total_latency_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        experiment_id,
                        rec.case_id,
                        rec.case.title,
                        rec.case.user_prompt,
                        1 if rec.case.is_attack else 0,
                        rec.case.paradigm.value,
                        rec.case.risk_category.value,
                        rec.proposal.tool_name,
                        json.dumps(rec.proposal.arguments),
                        1 if rec.proposal.is_valid else 0,
                        rec.proposal.proposal_latency_ms,
                        rec.defense_decision.decision.value,
                        rec.defense_decision.reason_code,
                        rec.defense_decision.explanation,
                        rec.defense_decision.latency_ms,
                        1 if rec.execution.executed else 0,
                        1 if rec.execution.attack_succeeded else 0,
                        1 if rec.execution.benign_completed else 0,
                        rec.total_latency_ms,
                    ),
                )

            # 3. Insert summary report
            conn.execute(
                """
                INSERT OR REPLACE INTO experiment_reports
                (experiment_id, asr, asr_lower, asr_upper, tcr, tcr_lower, tcr_upper,
                 fpr, dbr, median_latency_ms, p95_latency_ms, report_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    report.attack_success_rate.point_estimate,
                    report.attack_success_rate.ci_lower,
                    report.attack_success_rate.ci_upper,
                    report.benign_completion_rate.point_estimate,
                    report.benign_completion_rate.ci_lower,
                    report.benign_completion_rate.ci_upper,
                    report.false_positive_rate.point_estimate,
                    report.defense_block_rate.point_estimate,
                    report.median_total_latency_ms,
                    report.p95_total_latency_ms,
                    report.model_dump_json(),
                ),
            )
            conn.commit()

    def list_experiments(self) -> list[dict[str, Any]]:
        """List all experiments with summary metrics."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT e.id, e.title, e.defense_name, e.model_provider, e.model_name,
                       e.total_cases, e.created_at,
                       r.asr, r.asr_lower, r.asr_upper,
                       r.tcr, r.tcr_lower, r.tcr_upper,
                       r.fpr, r.dbr, r.median_latency_ms, r.p95_latency_ms
                FROM experiments e
                LEFT JOIN experiment_reports r ON e.id = r.experiment_id
                ORDER BY e.created_at DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_experiment_details(self, experiment_id: str) -> dict[str, Any] | None:
        """Get experiment metadata, report, and individual case telemetry records."""
        with self.db.get_connection() as conn:
            exp_row = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
            if not exp_row:
                return None

            report_row = conn.execute("SELECT * FROM experiment_reports WHERE experiment_id = ?", (experiment_id,)).fetchone()
            case_rows = conn.execute("SELECT * FROM case_records WHERE experiment_id = ? ORDER BY id ASC", (experiment_id,)).fetchall()

            exp_dict = dict(exp_row)
            exp_dict["config"] = json.loads(exp_dict["config_json"])
            exp_dict["report"] = json.loads(report_row["report_json"]) if report_row else None
            exp_dict["cases"] = [dict(c) for c in case_rows]
            return exp_dict

    def save_fuzz_run(self, result: FuzzRunResult) -> None:
        """Persist an adaptive fuzzing evaluation result."""
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO fuzz_runs
                (id, defense_name, seed, mutations_count, delta_asr, delta_tcr, delta_fpr, summary, full_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.fuzz_run_id,
                    result.defense_name,
                    result.seed,
                    result.mutations_count,
                    result.delta_asr,
                    result.delta_tcr,
                    result.delta_fpr,
                    result.evasion_summary,
                    result.model_dump_json(),
                ),
            )
            conn.commit()

    def list_fuzz_runs(self) -> list[dict[str, Any]]:
        """List all recorded adaptive fuzzing runs."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM fuzz_runs ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_fuzz_run(self, fuzz_run_id: str) -> dict[str, Any] | None:
        """Get full details of a specific fuzz run."""
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM fuzz_runs WHERE id = ?", (fuzz_run_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res["details"] = json.loads(res["full_json"])
            return res


repo = ExperimentRepository()
