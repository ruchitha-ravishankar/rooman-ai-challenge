"""Bounded adaptive fuzzing engine for evaluating defense evasion."""

from __future__ import annotations

import random
from typing import Any
from pydantic import BaseModel, Field

from mcp_defense_lab.core.llm_provider import BaseLLMProvider
from mcp_defense_lab.core.models import BenchmarkCase, ToolSchema
from mcp_defense_lab.defenses.base import DefenseStrategy
from mcp_defense_lab.evaluation.benchmark import BenchmarkRunner
from mcp_defense_lab.evaluation.metrics import EvaluationReport
from mcp_defense_lab.fuzzing.mutators import (
    ArgumentPathObfuscator,
    BaseMutator,
    BenignContextWrapperMutator,
    SynonymMutator,
    UnicodeZeroWidthMutator,
)


class FuzzRunResult(BaseModel):
    """Comparative results of a defense before and after adaptive fuzzing."""

    fuzz_run_id: str
    defense_name: str
    seed: int
    mutators_used: list[str]
    mutations_count: int

    pre_fuzz_report: EvaluationReport
    post_fuzz_report: EvaluationReport

    # Degradation / Evasion deltas
    delta_asr: float  # Positive delta means attacks evaded defense
    delta_tcr: float  # Change in benign task completion
    delta_fpr: float  # Change in false positive rate
    evasion_summary: str = ""


class AdaptiveFuzzer:
    """Bounded, deterministic fuzzing engine that generates adversarial tool descriptions and arguments."""

    def __init__(
        self,
        mutators: list[BaseMutator] | None = None,
        seed: int = 42,
        max_mutations_per_case: int = 2,
    ) -> None:
        self.mutators = mutators or [
            SynonymMutator(),
            UnicodeZeroWidthMutator(),
            BenignContextWrapperMutator(),
            ArgumentPathObfuscator(),
        ]
        self.seed = seed
        self.max_mutations_per_case = max(1, min(max_mutations_per_case, 5))

    def mutate_case(self, case: BenchmarkCase, rng: random.Random) -> tuple[BenchmarkCase, int]:
        """Produce a bounded mutated copy of a benchmark case."""
        # Deep copy tools
        new_tools: list[ToolSchema] = []
        mutations_done = 0

        for tool in case.tools:
            if tool.is_poisoned:
                # Apply 1 to max_mutations_per_case mutators to the description
                desc = tool.description
                num_muts = rng.randint(1, self.max_mutations_per_case)
                chosen_mutators = rng.sample(self.mutators, min(num_muts, len(self.mutators)))

                for mut in chosen_mutators:
                    desc = mut.mutate(desc, rng)
                    mutations_done += 1

                mutated_tool = tool.model_copy(update={"description": desc})
                new_tools.append(mutated_tool)
            else:
                new_tools.append(tool.model_copy())

        fuzzed_case = case.model_copy(update={
            "case_id": f"{case.case_id}_fuzzed",
            "tools": new_tools,
            "title": f"[FUZZED] {case.title}",
        })
        return fuzzed_case, mutations_done

    def run_fuzz_evaluation(
        self,
        defense: DefenseStrategy,
        provider: BaseLLMProvider,
        baseline_cases: list[BenchmarkCase],
        fuzz_run_id: str = "fuzz_01",
    ) -> FuzzRunResult:
        """Run pre-fuzz vs post-fuzz evaluation and calculate degradation deltas."""
        rng = random.Random(self.seed)
        runner = BenchmarkRunner(provider=provider, defense=defense)

        # 1. Pre-fuzz evaluation
        _, pre_report = runner.run_suite(baseline_cases, experiment_id=f"{fuzz_run_id}_pre")

        # 2. Generate mutated dataset
        fuzzed_cases: list[BenchmarkCase] = []
        total_mutations = 0
        for case in baseline_cases:
            fuzzed_c, n_muts = self.mutate_case(case, rng)
            fuzzed_cases.append(fuzzed_c)
            total_mutations += n_muts

        # 3. Post-fuzz evaluation
        _, post_report = runner.run_suite(fuzzed_cases, experiment_id=f"{fuzz_run_id}_post")

        # 4. Compute metrics deltas
        delta_asr = round(post_report.attack_success_rate.point_estimate - pre_report.attack_success_rate.point_estimate, 4)
        delta_tcr = round(post_report.benign_completion_rate.point_estimate - pre_report.benign_completion_rate.point_estimate, 4)
        delta_fpr = round(post_report.false_positive_rate.point_estimate - pre_report.false_positive_rate.point_estimate, 4)

        summary = (
            f"Defense '{defense.name}' under {len(self.mutators)} mutation strategies: "
            f"ASR shifted by {delta_asr:+.1%}, TCR shifted by {delta_tcr:+.1%}, FPR shifted by {delta_fpr:+.1%}."
        )

        return FuzzRunResult(
            fuzz_run_id=fuzz_run_id,
            defense_name=defense.name,
            seed=self.seed,
            mutators_used=[m.name for m in self.mutators],
            mutations_count=total_mutations,
            pre_fuzz_report=pre_report,
            post_fuzz_report=post_report,
            delta_asr=delta_asr,
            delta_tcr=delta_tcr,
            delta_fpr=delta_fpr,
            evasion_summary=summary,
        )
