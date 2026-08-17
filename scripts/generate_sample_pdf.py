"""Generates a sample academic PDF paper for testing PDF ingestion in VeriCite AI."""

import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCES_DIR = BASE_DIR / "data" / "sources"
PDF_PATH = SOURCES_DIR / "autonomous_ai_agents_safety.pdf"


def generate_pdf():
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        spaceAfter=12
    )
    h2_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        spaceBefore=14,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        spaceAfter=8
    )

    story = []

    # Title
    story.append(Paragraph("Autonomous AI Agents: Alignment Guardrails, Tool-Use Sandboxing, and Verifiable Action Traces", title_style))
    story.append(Paragraph("<b>Technical Whitepaper — Stanford & DeepMind Safety Collective</b>", body_style))
    story.append(Spacer(1, 10))

    # Section 1
    story.append(Paragraph("1. Agentic Sandboxing and Tool Execution Verification", h2_style))
    story.append(Paragraph(
        "Autonomous AI agent frameworks require hardware-isolated runtime sandboxes (e.g. gVisor microVMs or WebAssembly runtimes) "
        "to prevent unauthorized lateral network traversal during autonomous code execution. By enforcing strict capability-based "
        "security permissions and cryptographic action signing, agent platforms limit memory consumption to 512MB per container "
        "and enforce a strict 30-second execution wall-clock timeout on all generated shell commands.",
        body_style
    ))

    # Section 2
    story.append(Paragraph("2. Dual-Verification Red Teaming and Constitutional AI", h2_style))
    story.append(Paragraph(
        "To mitigate prompt injection and reward hacking, Verifiable Constitutional Guardrails evaluate all intermediate reasoning steps "
        "using dual-critic verification models. In empirical safety benchmarks, dual-verification architectures reduced adversarial jailbreak "
        "susceptibility by 94.2% while maintaining 99.8% task completion fidelity across multi-turn API tool executions.",
        body_style
    ))

    # Section 3
    story.append(Paragraph("3. Immutable Provenance Audit Trails", h2_style))
    story.append(Paragraph(
        "Every decision branch in the agent thought tree is recorded in an append-only JSONL log containing token probabilities, "
        "retrieved source chunk hashes, and tool return payloads. This enables post-hoc forensic auditing and automated compliance "
        "verification under the IEEE P7000 standard for autonomous system transparency.",
        body_style
    ))

    doc.build(story)
    print(f"Generated sample PDF at: {PDF_PATH}")


if __name__ == "__main__":
    generate_pdf()
