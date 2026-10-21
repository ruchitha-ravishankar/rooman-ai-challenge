"""Unit tests for bounded adaptive fuzzing engine and adversarial mutators."""

import random
import pytest
from mcp_defense_lab.core.llm_provider import ScriptedBehaviorMode, ScriptedFakeModelProvider
from mcp_defense_lab.defenses.keyword import KeywordRuleScanner
from mcp_defense_lab.evaluation.datasets import generate_synthetic_benchmark
from mcp_defense_lab.fuzzing.fuzzer import AdaptiveFuzzer
from mcp_defense_lab.fuzzing.mutators import (
    ArgumentPathObfuscator,
    BenignContextWrapperMutator,
    SynonymMutator,
    UnicodeZeroWidthMutator,
)


def test_synonym_mutator():
    mut = SynonymMutator()
    rng = random.Random(42)
    original = "You must execute this command."
    mutated = mut.mutate(original, rng)
    assert mutated != original
    assert any(syn in mutated.lower() for syn in ["mandated", "required", "invoke", "trigger", "shall"])


def test_unicode_zero_width_mutator():
    mut = UnicodeZeroWidthMutator()
    rng = random.Random(42)
    original = "execute read_file immediately"
    mutated = mut.mutate(original, rng)
    # Check that at least one zero-width char was inserted
    assert any(zw in mutated for zw in mut.ZERO_WIDTH_CHARS)


def test_benign_context_wrapper_mutator():
    mut = BenignContextWrapperMutator()
    rng = random.Random(42)
    directive = "read /etc/shadow"
    wrapped = mut.mutate(directive, rng)
    assert directive in wrapped
    assert "compliance" in wrapped.lower() or "audit" in wrapped.lower() or "iso" in wrapped.lower()


def test_argument_path_obfuscator():
    mut = ArgumentPathObfuscator()
    rng = random.Random(42)
    path = "/home/user/documents/report.csv"
    obf = mut.mutate(path, rng)
    assert "/home/./user" in obf


def test_fuzzer_seed_reproducibility():
    cases = generate_synthetic_benchmark()[:5]
    fuzzer1 = AdaptiveFuzzer(seed=123)
    fuzzer2 = AdaptiveFuzzer(seed=123)

    c1, _ = fuzzer1.mutate_case(cases[0], random.Random(123))
    c2, _ = fuzzer2.mutate_case(cases[0], random.Random(123))

    assert c1.tools[0].description == c2.tools[0].description


def test_fuzzer_end_to_end_run():
    cases = generate_synthetic_benchmark()[:10]
    defense = KeywordRuleScanner()
    provider = ScriptedFakeModelProvider(mode=ScriptedBehaviorMode.NAIVE_COMPLIANT)

    fuzzer = AdaptiveFuzzer(seed=42, max_mutations_per_case=2)
    res = fuzzer.run_fuzz_evaluation(defense=defense, provider=provider, baseline_cases=cases)

    assert res.pre_fuzz_report.total_cases == 10
    assert res.post_fuzz_report.total_cases == 10
    assert isinstance(res.delta_asr, float)
    assert res.mutations_count > 0
