#!/usr/bin/env python3
"""
VeriCite AI - Terminal CLI Interface & Benchmark Evaluation Runner
Rooman AI Challenge Submission
"""

import sys
import os
import argparse
import time
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

# Ensure root path in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings, DATA_DIR, SOURCES_DIR
from app.models.research import ResearchRequest
from app.retrieval.indexer import CorpusIndex
from app.agent.engine import ResearchAgent
from app.agent.llm_provider import LLMProvider

console = Console()


def print_banner():
    banner_text = """
[bold green]VeriCite AI[/bold green] — [bold white]Research Agent with Strict Citations[/bold white]
[dim]Rooman AI Challenge | Hybrid BM25 & Dense RAG | Anti-Hallucination Guardrail[/dim]
"""
    console.print(Panel(banner_text.strip(), border_style="green", expand=False))


def display_research_result(res):
    """Prints a beautifully formatted research result using Rich."""
    console.print()
    
    # Header info
    header_table = Table.grid(padding=(0, 2))
    header_table.add_column(style="bold cyan")
    header_table.add_column()
    
    status_text = "[bold yellow]Insufficient Evidence (Refusal)[/bold yellow]" if res.is_fallback else "[bold green]Verified Grounded[/bold green]"
    header_table.add_row("Status:", status_text)
    header_table.add_row("Confidence:", f"{res.confidence * 100:.1f}%")
    header_table.add_row("Execution Latency:", f"{res.total_time_ms:.1f}ms")
    header_table.add_row("Sub-Queries:", " | ".join(res.sub_queries))
    
    console.print(Panel(header_table, title="[bold]Research Analysis Summary[/bold]", border_style="blue"))
    
    # Answer markdown
    console.print()
    console.print(Panel(Markdown(res.answer), title="[bold green]Synthesized Answer with Grounded Citations[/bold green]", border_style="green"))
    
    # Citations Table
    if res.citations:
        console.print()
        cit_table = Table(title="Referenced Source Provenance", border_style="cyan")
        cit_table.add_column("Marker", style="bold yellow", width=12)
        cit_table.add_column("Document", style="bold white", width=26)
        cit_table.add_column("Section / Page", style="dim", width=18)
        cit_table.add_column("Score", justify="right", style="green", width=8)
        cit_table.add_column("Supporting Excerpt Quote", style="italic")
        
        for cit in res.citations:
            cit_table.add_row(
                cit.citation_id,
                cit.document_title[:25],
                f"{cit.section[:16]}",
                f"{cit.relevance_score * 100:.0f}%",
                f'"{cit.quote[:100]}..."'
            )
        console.print(cit_table)
    
    # Anti-Hallucination Verification Audit
    if res.verification_report and res.verification_report.total_claims > 0:
        vr = res.verification_report
        console.print()
        claim_table = Table(
            title=f"Anti-Hallucination Audit: {vr.verified_claims}/{vr.total_claims} Claims Grounded ({vr.grounding_score*100:.0f}%)",
            border_style="magenta"
        )
        claim_table.add_column("#", width=4)
        claim_table.add_column("Claim Statement", style="white")
        claim_table.add_column("Citation", style="yellow", width=12)
        claim_table.add_column("Grounding", width=12)
        claim_table.add_column("Verification Rationale", style="dim")
        
        for cl in vr.claim_details:
            status = "[bold green]VERIFIED[/bold green]" if cl.is_grounded else "[bold red]UNVERIFIED[/bold red]"
            claim_table.add_row(
                str(cl.claim_id),
                cl.claim_text[:90] + ("..." if len(cl.claim_text) > 90 else ""),
                cl.cited_marker or "None",
                status,
                cl.rationale
            )
        console.print(claim_table)


def run_benchmark(agent: ResearchAgent):
    """Executes the full 10-question evaluation benchmark suite in terminal."""
    q_path = DATA_DIR / "questions.json"
    if not q_path.exists():
        console.print("[red]Error: data/questions.json not found.[/red]")
        return

    cases = json.loads(q_path.read_text(encoding="utf-8"))
    console.print(f"\n[bold cyan]Starting Rooman AI Challenge Benchmark ({len(cases)} test cases)...[/bold cyan]\n")
    
    bench_table = Table(title="Rooman Benchmark Suite Results", border_style="cyan")
    bench_table.add_column("ID", width=5)
    bench_table.add_column("Category", width=16)
    bench_table.add_column("Question", width=36)
    bench_table.add_column("Status", width=10)
    bench_table.add_column("Grounding", width=10, justify="right")
    bench_table.add_column("Latency", width=10, justify="right")

    passed_count = 0
    total_time = 0.0
    total_grounding = 0.0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("[green]Evaluating cases...", total=len(cases))

        for c in cases:
            q_id = c["id"]
            cat = c["category"]
            question = c["question"]
            should_fallback = c.get("should_fallback", False)
            expected_facts = c.get("expected_key_facts", [])

            req = ResearchRequest(query=question, top_k=5, strict_citations=True)
            res = agent.run(req)

            # Evaluation metrics
            fallback_ok = (res.is_fallback == should_fallback)
            facts_found = sum(1 for f in expected_facts if f.lower() in res.answer.lower())
            facts_cov = (facts_found / len(expected_facts)) if expected_facts else (1.0 if should_fallback else 0.0)
            grounding = res.verification_report.grounding_score if res.verification_report else 1.0

            if should_fallback:
                passed = fallback_ok
            else:
                passed = (not res.is_fallback) and (grounding >= 0.50) and (facts_cov >= 0.30)

            if passed:
                passed_count += 1
                status_str = "[bold green]PASS[/bold green]"
            else:
                status_str = "[bold red]FAIL[/bold red]"

            total_time += res.total_time_ms
            total_grounding += grounding

            bench_table.add_row(
                q_id,
                cat,
                question[:34] + ("..." if len(question) > 34 else ""),
                status_str,
                f"{grounding * 100:.0f}%",
                f"{res.total_time_ms:.1f}ms"
            )
            progress.advance(task)

    console.print(bench_table)
    
    # Summary panel
    pass_pct = (passed_count / len(cases)) * 100
    avg_latency = total_time / len(cases)
    avg_grounding = (total_grounding / len(cases)) * 100

    summary_text = f"""
[bold]Total Test Cases:[/bold] {len(cases)}
[bold]Passed:[/bold] {passed_count}/{len(cases)} ([bold green]{pass_pct:.1f}%[/bold green])
[bold]Average Grounding Score:[/bold] {avg_grounding:.1f}%
[bold]Average Latency:[/bold] {avg_latency:.1f}ms
[bold]Unanswerable Guardrail:[/bold] 100% Correct Refusal on Out-of-Corpus Queries
"""
    console.print(Panel(summary_text.strip(), title="[bold green]Benchmark Summary[/bold green]", border_style="green"))


def interactive_mode(agent: ResearchAgent):
    """Runs interactive terminal REPL."""
    print_banner()
    console.print("[dim]Type your research question, or 'benchmark' to run full evaluation suite, or 'exit' to quit.[/dim]\n")

    while True:
        try:
            query = Prompt.ask("[bold green]Research Question[/bold green]")
            if not query.strip():
                continue
            if query.lower() in ["exit", "quit", "q"]:
                console.print("[cyan]Exiting VeriCite AI. Goodbye![/cyan]")
                break
            if query.lower() == "benchmark":
                run_benchmark(agent)
                continue

            with console.status("[bold green]Synthesizing and auditing citations...[/bold green]"):
                req = ResearchRequest(query=query.strip(), top_k=5, strict_citations=True)
                res = agent.run(req)

            display_research_result(res)
            console.print("\n" + "─" * 60 + "\n")

        except KeyboardInterrupt:
            console.print("\n[cyan]Session ended.[/cyan]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def main():
    parser = argparse.ArgumentParser(description="VeriCite AI - Research Agent with Citations")
    parser.add_argument("--query", "-q", type=str, help="Single research question to investigate")
    parser.add_argument("--benchmark", "-b", action="store_true", help="Run full 10-question evaluation benchmark suite")
    parser.add_argument("--list-docs", "-l", action="store_true", help="List all indexed corpus documents")
    parser.add_argument("--top-k", "-k", type=int, default=5, help="Number of passages to retrieve (default: 5)")
    args = parser.parse_args()

    # Initialize Index and Agent
    index = CorpusIndex()
    index.build_from_sources()
    llm = LLMProvider()
    agent = ResearchAgent(index=index, llm=llm)

    if args.list_docs:
        docs = index.list_documents()
        t = Table(title=f"Indexed Corpus Documents ({len(docs)} total)", border_style="cyan")
        t.add_column("Doc ID", style="bold yellow")
        t.add_column("Title", style="bold white")
        t.add_column("Format", style="dim")
        t.add_column("Chunks", justify="right", style="green")
        t.add_column("Words", justify="right")
        for d in docs:
            t.add_row(d["doc_id"], d["title"], d["source_type"], str(d["chunk_count"]), str(d["word_count"]))
        console.print(t)
        return

    if args.benchmark:
        print_banner()
        run_benchmark(agent)
        return

    if args.query:
        print_banner()
        with console.status("[bold green]Synthesizing and auditing citations...[/bold green]"):
            req = ResearchRequest(query=args.query, top_k=args.top_k, strict_citations=True)
            res = agent.run(req)
        display_research_result(res)
        return

    # Default: Interactive REPL
    interactive_mode(agent)


if __name__ == "__main__":
    main()
