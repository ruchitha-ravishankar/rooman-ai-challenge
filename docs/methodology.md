# Evaluation Methodology: Measuring MCP Defenses

## 1. Scientific Objective

The core objective of **MCP Defense Lab** is to measure the defensive efficacy and utility trade-offs of security mechanisms defending tool-calling AI agents against **Tool Poisoning Attacks (TPA)**.

A viable defense must achieve two concurrent goals:
1. **Minimize Attack Success Rate (ASR)**: Intercept malicious actions induced by poisoned tool metadata.
2. **Maximize Benign Task Completion Rate (TCR)**: Avoid falsely blocking legitimate user requests (maintaining Low False Positive Rate, FPR).

---

## 2. Experimental Protocol

Each evaluation trial executes a standardized, single-turn tool-calling protocol:

1. **Context Formulation**: The agent runtime is initialized with a user query \(Q\) and a set of available tool schemas \(\{T_1, T_2, \dots, T_k\}\). In attack cases, exactly one tool description contains a poisoned directive \(D_{\text{poison}}\).
2. **Model Proposal**: The model proposes a single JSON-formatted tool call:
   \[
   P = \{\text{"tool\_name"}: T_i, \text{"arguments"}: \{k_1: v_1, \dots\}\}
   \]
3. **Proposal Validation**: The framework validates that \(P\) adheres to valid JSON syntax, targets an existent tool, and provides structured arguments. Malformed proposals are recorded with `is_valid=False` and excluded from the ASR denominator.
4. **Defense Evaluation**: The candidate proposal \(P\) is routed to the configured defense strategy \(D\), which outputs:
   \[
   \text{Decision}(P) \in \{\text{ALLOW}, \text{BLOCK}, \text{ABSTAIN}\}
   \]
   accompanied by a structured reason code, explanation, and wall-clock inspection latency.
5. **Simulated Execution**: If allowed, \(P\) executes inside `SafeSimulator`. The simulator logs all attempted side effects (VFS file reads/writes, mock command executions, mock network egress).
6. **Ground-Truth Adjudication**:
   - For attack cases: Succeeded if harmful side effects occurred or if target signature was matched.
   - For benign cases: Succeeded if expected benign tool executed without errors.

---

## 3. Defense Implementations Compared

| Defense Strategy | Type | Mechanism | Primary Trade-Off |
| :--- | :--- | :--- | :--- |
| **No-Defense Baseline** | Audit Control | Allows all proposals through to safe simulator. | Baseline vulnerability reference (high ASR). |
| **Keyword Rule Scanner** | Deterministic Regex | Scans for known prompt injection phrases and sensitive targets (`id_rsa`, `/etc/shadow`). | Fast (\(<0.1\text{ ms}\)), but vulnerable to paraphrase evasion. |
| **LLM Judge Scanner** | Model-based | Secondary evaluator prompt inspecting tool proposal and description. | Flexible, but introduces inference latency and prompt overhead. |
| **Schema Pinning & RBAC** | Architectural / Cryptographic | Hashes tool schemas; restricts capabilities based on task profile. | Strong against rug pulls; may over-restrict dynamic workflows. |
| **Intent-Alignment Defense** | Semantic / Lexical Grounding | Evaluates tool relevance, argument grounding, and unprompted side effects. | High mitigation, zero false positives on standard benign tasks, fail-closed on ambiguity. |

---

## 4. Reproducibility & Control Variables

To eliminate variance during automated testing and CI:
- **Seed Control**: All random number generators (mutators, case selection) are initialized with a deterministic seed (default `42`).
- **Offline Determinism**: Uses `ScriptedFakeModelProvider` to guarantee consistent, network-independent behavioral responses across test runs.
- **Isolated State**: The simulator is reset between every trial (`simulator.reset()`) to prevent state pollution across benchmark cases.
