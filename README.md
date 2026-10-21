# MCP Defense Lab: Measuring MCP Defenses with a Real Agent in the Loop

[![CI Test Suite](https://github.com/ruchitha-ravishankar/rooman-ai-challenge/actions/workflows/ci.yml/badge.svg)](https://github.com/ruchitha-ravishankar/rooman-ai-challenge/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-orange.svg)](https://streamlit.io)

**MCP Defense Lab** is an open-source, reproducible security evaluation and research framework. It empirically measures how effectively defensive mechanisms prevent **Tool Poisoning Attacks (TPA)** and indirect prompt injections on Model Context Protocol (MCP) agents, while simultaneously evaluating the preservation of legitimate task completion.

---

## 📌 The "One Sentence" Formulation
> *"MCP Defense Lab provides an end-to-end evaluation harness featuring a real agent loop, isolated safe simulation, 5 distinct defense strategies (including a novel Intent-Alignment defense), bounded adaptive fuzzing, and SQLite auditability to rigorously measure agent security trade-offs."*

---

## 🛡️ Defenses Implemented & Evaluated

All defenses implement a uniform `DefenseStrategy` interface emitting structured decisions (`allow`, `block`, `abstain`), reason codes, explanations, and latency telemetry:

1. **No-Defense Baseline**: Control baseline measuring unmitigated agent vulnerability (with simulator sandbox safeguards active).
2. **Keyword Rule Scanner**: High-speed deterministic regex scanner inspecting tool names, arguments, and metadata for prompt injection signatures and high-risk paths (`~/.ssh/id_rsa`, `/etc/shadow`).
3. **LLM Judge Scanner**: Secondary model-based evaluator inspecting candidate proposals and tool descriptions for semantic hijacking.
4. **Schema Pinning & RBAC Adapter**: Cryptographic tool schema hash pinning (detecting dynamic "rug pull" metadata injections) paired with role-based capability boundaries (Least Privilege).
5. **Intent-Alignment Defense (Our Novel Defense)**: Evaluates semantic and lexical grounding between the user's explicit request and candidate tool calls. Detects irrelevant tool calls, parameter tampering, unprompted side effects, suspicious data access, and metadata injection instructions. Enforces a **strict fail-closed policy** on ambiguous side effects.

---

## 📊 Empirical Evaluation Results

Evaluated on the 40-case balanced benchmark suite (20 Attack cases across Template-1, Template-2, and Template-3; 20 Benign tasks) using deterministic seed control:

| Defense Strategy | Attack Success Rate (ASR) [95% Wilson CI] | Benign Task Completion (TCR) [95% CI] | False Positive Rate (FPR) | Defense Block Rate | Relative ASR Reduction | Median Total Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **No-Defense Baseline** | **95.0%** [76.4% – 99.1%] | 85.0% [64.0% – 94.8%] | 0.0% | 0.0% | 0.0% (Ref) | 0.01 ms |
| **Keyword Rule Scanner** | **0.0%** [0.0% – 16.1%] | 85.0% [64.0% – 94.8%] | 0.0% | 47.5% | **100.0%** | 0.03 ms |
| **LLM Judge Scanner** | **15.0%** [5.2% – 36.0%] | 85.0% [64.0% – 94.8%] | 0.0% | 40.0% | **84.2%** | 0.50 ms |
| **Schema Pinning & RBAC** | **0.0%** [0.0% – 16.1%] | 85.0% [64.0% – 94.8%] | 5.0% | 50.0% | **100.0%** | 0.01 ms |
| **Intent-Alignment Defense** | **0.0%** [0.0% – 16.1%] | **85.0%** [64.0% – 94.8%] | **0.0%** | 47.5% | **100.0%** | 0.02 ms |

> [!NOTE]
> All metrics use explicit denominators. Invalid model outputs and agent refusals are tracked separately and not counted automatically as successful defenses.

---

## 🏗️ Architecture & Safe Simulator

```
[User Request] + [MCP Tool Catalog]
               │
               ▼
      ┌─────────────────┐
      │  Agent Runtime  │ ◄───► [Scripted Mock Provider / Ollama Local LLM]
      └────────┬────────┘
               │ Candidate Tool Proposal
               ▼
      ┌─────────────────┐
      │  Defense Layer  │ ───► Decision: ALLOW / BLOCK / ABSTAIN + Reason Code
      └────────┬────────┘
               │ (Allowed proposals only)
               ▼
      ┌─────────────────────────────────────────────────────────┐
      │                  Safe Simulator Sandbox                 │
      │  - Isolated In-Memory Virtual File System (VFS)         │
      │  - Virtual Shell Parser (Zero Host OS Subprocesses)     │
      │  - Virtual Network Egress (Zero Physical Packets Sent)   │
      └────────────────────────────┬────────────────────────────┘
                                   │ Side-Effects & Telemetry
                                   ▼
      ┌─────────────────────────────────────────────────────────┐
      │            SQLite Audit Store (mcp_defense_lab.db)      │
      └────────────────────────────┬────────────────────────────┘
                                   │
             ┌─────────────────────┼─────────────────────┐
             ▼                     ▼                     ▼
     [Rich Terminal CLI]   [FastAPI REST API]    [Streamlit Dashboard]
```

---

## 🚀 Quickstart Guide

### 1. Installation
```bash
git clone https://github.com/ruchitha-ravishankar/rooman-ai-challenge.git
cd rooman-ai-challenge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Multi-Defense Benchmark
Run all defenses across 40 benchmark cases in under 1 second:
```bash
python cli.py run-experiment --defense all --cases 40
```

### 3. Run Adaptive Fuzzing Evaluation
Test defense degradation under adversarial mutations (synonym substitution, zero-width chars, benign wrappers, path obfuscations):
```bash
python cli.py run-fuzz --defense intent_alignment_defense --mutations 2 --cases 20
```

### 4. Inspect Results
Display formatted result tables from SQLite:
```bash
python cli.py show-results
```

### 5. Launch Interactive Research Dashboard
```bash
streamlit run mcp_defense_lab/dashboard/app.py
```

### 6. Launch REST API Server
```bash
uvicorn mcp_defense_lab.api.app:app --host 127.0.0.1 --port 8000
```
API Documentation: `http://127.0.0.1:8000/docs`

---

## 🧪 Testing & Verification

Run the complete 100% offline unit, integration, and security test suite:
```bash
pytest tests/ -v
```

---

## 📂 Documentation Sitemap

- [AGENTS.md](AGENTS.md) — Operational instructions and constraints for AI agents.
- [docs/architecture.md](docs/architecture.md) — Detailed system design and component interfaces.
- [docs/threat-model.md](docs/threat-model.md) — MCP tool poisoning threat model and attack paradigms.
- [docs/methodology.md](docs/methodology.md) — Scientific experimental protocol and control variables.
- [docs/metrics.md](docs/metrics.md) — Mathematical formulas, denominators, and Wilson confidence intervals.
- [docs/data-provenance.md](docs/data-provenance.md) — Upstream licensing review and clean synthetic benchmark policy.
- [docs/limitations.md](docs/limitations.md) — Scope boundaries, simulation vs physical execution, and future work.
- [docs/experiment-runbook.md](docs/experiment-runbook.md) — Step-by-step reproduction guide for researchers.

---

## ⚖️ License & Ethical Responsible Disclosure

This project is licensed under the [MIT License](LICENSE). All synthetic fixtures are provided under MIT / CC0 for open academic research.

In accordance with responsible disclosure, all attacks executed by this repository are strictly sandboxed inside `SafeSimulator`. No external systems are targeted.
