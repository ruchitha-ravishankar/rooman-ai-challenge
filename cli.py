#!/usr/bin/env python3
"""MCP Defense Lab — Command Line Interface & Evaluation Runner.

Measuring MCP Defenses with a Real Agent in the Loop.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mcp_defense_lab.core.llm_provider import (
    OllamaProvider,
    ScriptedBehaviorMode,
    ScriptedFakeModelProvider,
)
from mcp_defense_lab.db.repository import repo
from mcp_defense_lab.defenses import DEFENSE_REGISTRY, get_defense, list_available_defenses
from mcp_defense_lab.evaluation.benchmark import BenchmarkRunner
from mcp_defense_lab.evaluation.datasets import generate_synthetic_benchmark
from mcp_defense_lab.fuzzing.fuzzer import AdaptiveFuzzer
from mcp_defense_lab.fuzzing.mutators import (
    ArgumentPathObfuscator,
    BenignContextWrapperMutator,
    SynonymMutator,
    UnicodeZeroWidthMutator,
)

console = Console()


def print_banner() -> None:
    text = (
        "[bold cyan]MCP Defense Lab[/bold cyan] — [bold white]Measuring MCP Defenses with a Real Agent in the Loop[/bold white]\n"
        "[dim]Agent-Based Security Benchmark | Tool Poisoning Defenses | Bounded Adaptive Fuzzing[/dim]"
    )
    console.print(Panel(text.strip(), border_style="cyan", expand=False))


def cmd_health(args: argparse.Namespace) -> None:
    print_banner()
    ollama = OllamaProvider()
    ollama_ok = ollama.is_available()

    table = Table(title="System & Component Health Check", border_style="cyan")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    table.add_row("Database (SQLite)", "[green]READY[/green]", f"Path: {repo.db.db_path}")
    table.add_row(
        "Local LLM (Ollama)",
        "[green]AVAILABLE[/green]" if ollama_ok else "[yellow]OFFLINE / RESTRICTED[/yellow]",
        f"URL: {ollama._base_url} (Model: {ollama.model_name})",
    )
    table.add_row("Defenses Registered", f"[green]{len(DEFENSE_REGISTRY)} active[/green]", ", ".join(DEFENSE_REGISTRY.keys()))
    cases = generate_synthetic_benchmark()
    table.add_row("Synthetic Benchmark", f"[green]{len(cases)} cases[/green]", "20 Attacks (T1, T2, T3) + 20 Benign Tasks")

    console.print(table)


def cmd_list_defenses(args: argparse.Namespace) -> None:
    print_banner()
    table = Table(title="Available Defense Strategies", border_style="cyan")
    table.add_column("Defense Key", style="bold green")
    table.add_column("Name")
    table.add_column("Description")

    for d in list_available_defenses():
        table.add_row(d["id"], d["name"], d["description"])

    console.print(table)


def cmd_run_experiment(args: argparse.Namespace) -> None:
    print_banner()
    defenses_to_run = list(DEFENSE_REGISTRY.keys()) if args.defense == "all" else [args.defense]

    all_cases = generate_synthetic_benchmark()
    selected_cases = all_cases[:args.cases]

    # Model provider
    if args.provider == "ollama":
        provider = OllamaProvider(model_name=args.model)
        if not provider.is_available():
            console.print("[bold red]Error:[/bold red] Local Ollama server is offline or unreachable.")
            sys.exit(1)
        console.print(f"[bold green]Connected to live Ollama:[/bold green] model '{provider.model_name}'")
    else:
        mode_enum = ScriptedBehaviorMode(args.mode)
        provider = ScriptedFakeModelProvider(mode=mode_enum, model_name=args.model or f"scripted-{args.mode}")
        console.print(f"[bold cyan]Using Scripted Provider:[/bold cyan] mode='{args.mode}', model='{provider.model_name}'")

    baseline_asr = None

    # Run each defense
    for d_name in defenses_to_run:
        defense = get_defense(d_name)
        runner = BenchmarkRunner(provider=provider, defense=defense)
        exp_id = f"exp_{d_name[:6]}_{uuid.uuid4().hex[:6]}"

        console.print(f"\n[bold yellow]>>> Running Evaluation for Defense: {d_name} ({len(selected_cases)} cases)...[/bold yellow]")
        telemetry, report = runner.run_suite(selected_cases, experiment_id=exp_id, baseline_asr=baseline_asr)

        # Store baseline ASR if this was the baseline run
        if d_name == "no_defense_baseline":
            baseline_asr = report.attack_success_rate.point_estimate

        # Save to SQLite
        clean_config = {
            k: v for k, v in vars(args).items()
            if k != "func" and isinstance(v, (str, int, float, bool, list, dict, type(None)))
        }
        repo.save_experiment(
            experiment_id=exp_id,
            title=f"CLI Evaluation: {d_name}",
            defense_name=d_name,
            model_provider=provider.model_type,
            model_name=provider.model_name,
            config=clean_config,
            telemetry_records=telemetry,
            report=report,
        )

        console.print(f"[green]✓ Experiment {exp_id} saved to database.[/green]")
        console.print(f"  ASR: {report.attack_success_rate}")
        console.print(f"  TCR: {report.benign_completion_rate}")
        console.print(f"  FPR: {report.false_positive_rate}")
        console.print(f"  Defense Block Rate: {report.defense_block_rate}")
        console.print(f"  Median Latency: Total={report.median_total_latency_ms}ms | Defense={report.median_defense_latency_ms}ms")
        if report.relative_asr_reduction is not None:
            console.print(f"  Relative ASR Reduction vs Baseline: [bold green]{report.relative_asr_reduction:.1%}[/bold green]")


def cmd_run_fuzz(args: argparse.Namespace) -> None:
    print_banner()
    defense = get_defense(args.defense)
    provider = ScriptedFakeModelProvider(mode=ScriptedBehaviorMode.NAIVE_COMPLIANT)
    cases = generate_synthetic_benchmark()[:args.cases]

    console.print(f"[bold yellow]>>> Running Bounded Adaptive Fuzzing on '{args.defense}'...[/bold yellow]")
    console.print(f"    Cases: {len(cases)} | Max Mutations: {args.mutations} | Seed: {args.seed}")

    fuzzer = AdaptiveFuzzer(
        mutators=[
            SynonymMutator(),
            UnicodeZeroWidthMutator(),
            BenignContextWrapperMutator(),
            ArgumentPathObfuscator(),
        ],
        seed=args.seed,
        max_mutations_per_case=args.mutations,
    )

    fuzz_id = f"fuzz_{uuid.uuid4().hex[:8]}"
    result = fuzzer.run_fuzz_evaluation(defense=defense, provider=provider, baseline_cases=cases, fuzz_run_id=fuzz_id)
    repo.save_fuzz_run(result)

    console.print(f"\n[bold green]✓ Fuzz Run '{fuzz_id}' Complete & Persisted.[/bold green]")
    table = Table(title="Adaptive Fuzzing Evasion Results", border_style="cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Pre-Fuzz")
    table.add_column("Post-Fuzz")
    table.add_column("Evasion Delta", style="bold yellow")

    table.add_row("Attack Success Rate (ASR)", f"{result.pre_fuzz_report.attack_success_rate.point_estimate:.1%}", f"{result.post_fuzz_report.attack_success_rate.point_estimate:.1%}", f"{result.delta_asr:+.1%}")
    table.add_row("Benign Completion (TCR)", f"{result.pre_fuzz_report.benign_completion_rate.point_estimate:.1%}", f"{result.post_fuzz_report.benign_completion_rate.point_estimate:.1%}", f"{result.delta_tcr:+.1%}")
    table.add_row("False Positive Rate (FPR)", f"{result.pre_fuzz_report.false_positive_rate.point_estimate:.1%}", f"{result.post_fuzz_report.false_positive_rate.point_estimate:.1%}", f"{result.delta_fpr:+.1%}")

    console.print(table)
    console.print(f"[dim]{result.evasion_summary}[/dim]")


def cmd_show_results(args: argparse.Namespace) -> None:
    print_banner()
    exps = repo.list_experiments()
    if not exps:
        console.print("[yellow]No experiments recorded in SQLite database. Run 'python cli.py run-experiment' first.[/yellow]")
        return

    table = Table(title="Persisted Evaluation Experiments", border_style="cyan")
    table.add_column("Experiment ID", style="bold")
    table.add_column("Defense")
    table.add_column("Model Provider")
    table.add_column("Cases")
    table.add_column("ASR (Wilson 95% CI)", style="bold red")
    table.add_column("TCR (Benign)", style="bold green")
    table.add_column("FPR")
    table.add_column("Med Lat (ms)")

    for e in exps:
        asr_str = f"{e['asr']:.1%} [{e['asr_lower']:.1%}–{e['asr_upper']:.1%}]" if e['asr'] is not None else "N/A"
        tcr_str = f"{e['tcr']:.1%}" if e['tcr'] is not None else "N/A"
        fpr_str = f"{e['fpr']:.1%}" if e['fpr'] is not None else "N/A"
        med_lat = f"{e['median_latency_ms']:.1f}" if e['median_latency_ms'] is not None else "N/A"
        table.add_row(
            e["id"],
            e["defense_name"],
            e["model_provider"],
            str(e["total_cases"]),
            asr_str,
            tcr_str,
            fpr_str,
            med_lat,
        )

    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MCP Defense Lab — Measuring MCP Defenses with a Real Agent in the Loop",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # health
    p_health = subparsers.add_parser("health", help="Check system and component health")
    p_health.set_defaults(func=cmd_health)

    # list-defenses
    p_defenses = subparsers.add_parser("list-defenses", help="List all implemented defense strategies")
    p_defenses.set_defaults(func=cmd_list_defenses)

    # run-experiment
    p_exp = subparsers.add_parser("run-experiment", help="Run benchmark evaluation across defenses")
    p_exp.add_argument("--defense", default="intent_alignment_defense", help="Defense name or 'all'")
    p_exp.add_argument("--provider", default="scripted", choices=["scripted", "ollama"], help="Model provider")
    p_exp.add_argument("--model", default=None, help="Model identifier")
    p_exp.add_argument("--mode", default="naive_compliant", choices=["naive_compliant", "benign_optimal", "honest_refusing", "malformed_output"], help="Scripted provider behavior mode")
    p_exp.add_argument("--cases", type=int, default=40, help="Number of benchmark cases to evaluate")
    p_exp.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    p_exp.set_defaults(func=cmd_run_experiment)

    # run-fuzz
    p_fuzz = subparsers.add_parser("run-fuzz", help="Run bounded adaptive fuzzing evaluation")
    p_fuzz.add_argument("--defense", default="intent_alignment_defense", help="Defense to fuzz")
    p_fuzz.add_argument("--mutations", type=int, default=2, help="Max mutations per case")
    p_fuzz.add_argument("--cases", type=int, default=20, help="Sample count")
    p_fuzz.add_argument("--seed", type=int, default=42, help="Random seed")
    p_fuzz.set_defaults(func=cmd_run_fuzz)

    # show-results
    p_results = subparsers.add_parser("show-results", help="Display saved benchmark results from SQLite")
    p_results.set_defaults(func=cmd_show_results)

    parsed = parser.parse_args()
    parsed.func(parsed)


if __name__ == "__main__":
    main()
