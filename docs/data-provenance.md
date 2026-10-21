# Data Provenance, Licensing & Benchmark Policy

## 1. Upstream Investigation: MCPTox Benchmark

As mandated in Phase 1 of this project, we investigated the upstream MCPTox benchmark:
- **Inspect AI Wrapper**: [`https://github.com/stefanoamorelli/inspect-evals-mcptox`](https://github.com/stefanoamorelli/inspect-evals-mcptox) (MIT License)
- **Primary Upstream Benchmark Repository**: [`https://github.com/zhiqiangwang4/MCPTox-Benchmark`](https://github.com/zhiqiangwang4/MCPTox-Benchmark)
- **Academic Citation**: Wang et al., *"MCPTox: A Benchmark for Tool Poisoning Attack on Real-World MCP Servers"*, AAAI 2026 / arXiv:2508.14925.

### Licensing & Copyright Analysis
Our investigation revealed the following critical legal and ethical facts:
1. The inspect-evals wrapper code authored by Stefano Amorelli is licensed under the permissive **MIT License**.
2. However, the upstream primary dataset repository (`zhiqiangwang4/MCPTox-Benchmark`) contains **no explicit open-source software license file** (such as MIT, Apache 2.0, or CC-BY).
3. Under international copyright conventions (Berne Convention), when a creator makes code or data viewable on GitHub without an explicit license, **all rights are reserved by default to the authors**.
4. The inspect-evals repository README explicitly acknowledges this constraint:
   > *"The upstream benchmark is released publicly by the authors 'for the development of verifiably safer AI agents,' but the repository currently carries no explicit license. The data is fetched at runtime and not redistributed here."*

---

## 2. Redistribution Policy for MCP Defense Lab

In adherence to open-source licensing principles, legal compliance, and research reproducibility:

> [!IMPORTANT]
> **Zero Proprietary Data Bundling**:
> **MCP Defense Lab does NOT bundle, vendor, or redistribute raw benchmark data files** from `zhiqiangwang4/MCPTox-Benchmark`. Never assume third-party datasets are free to redistribute without an explicit grant of license.

---

## 3. Built-In Synthetic Clean-Room Benchmark Fixtures

To ensure that MCP Defense Lab functions out of the box with zero internet access, zero API keys, and 100% legal clarity, we developed an independent, clean-room synthetic benchmark suite:
- **License**: Released under the project's permissive **MIT License / CC0 public domain**.
- **Composition**: 40 balanced test cases:
  - **20 Attack Cases**: Covering all 3 MCPTox attack paradigms:
    - *Template-1 (Explicit Trigger Function Hijack)*: 7 cases (credential read, log deletion, exfiltration).
    - *Template-2 (Implicit Trigger Function Hijack)*: 6 cases (diagnostic redirection, telemetry exfil).
    - *Template-3 (Implicit Parameter Tampering)*: 7 cases (substituting file paths with `/etc/shadow`, credentials).
  - **20 Benign Tasks**: Real-world legitimate queries (math calculations, report reading, planning notes extraction, directory listings).
- **Risk Categorization**: Credential Leakage, Privacy Leakage, Infrastructure Damage, and Information Manipulation.

---

## 4. Optional Runtime Ingestion for External Datasets

For academic researchers holding legitimate access or fair-use research exemptions wishing to evaluate against upstream MCPTox:
1. Place downloaded JSON dataset files in `data/external/`.
2. Ensure SHA-256 integrity verification before running benchmarks.
3. Keep all external datasets out of Git version control (enforced via `.gitignore`).
