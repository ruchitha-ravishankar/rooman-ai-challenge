# Limitations & Scope Boundaries: MCP Defense Lab

## 1. Single-Turn vs. Multi-Turn Horizon

- **Current Scope**: MCP Defense Lab evaluates single-turn tool invocation decisions (one user query -> one tool-calling proposal). This aligns directly with the benchmark standard established in the MCPTox literature (AAAI 2026).
- **Limitation**: Real-world agents frequently execute complex multi-step trajectories (chains of 5 to 20 tool calls). An attack might remain dormant in early steps and only trigger exfiltration in later reasoning steps.
- **Future Direction**: Extending the agent loop to evaluate multi-turn trajectory state graphs and cumulative side-effect accumulation.

---

## 2. Simulated vs. Physical Execution

- **Current Scope**: All execution occurs strictly inside `SafeSimulator` (in-memory VFS, mock shell parser, mock network egress).
- **Safety Benefit**: Guarantees zero host risk; experiments will never wipe real disks, exfiltrate real private keys, or send real network packets.
- **Limitation**: Real-world operating systems feature nuances like symlink escapes, environment variable side channels, and subtle binary flag permutations that a mock parser might not exhaustively model.

---

## 3. Model Capacity & Instruction-Following Paradox

- **Empirical Observation**: As documented in the MCPTox research, more capable reasoning models (e.g. GPT-4o, Claude 3.5 Sonnet, o1) often exhibit **higher Attack Success Rates (ASR)** than weaker models when unmitigated. This occurs because frontier models possess superior instruction-following obedience and are more easily swayed by meta-directives disguised as system documentation.
- **Offline Mock Provider**: `ScriptedFakeModelProvider` provides deterministic simulation of these compliant behaviors for reproducible CI testing, but cannot replicate the stochastic edge cases of a live 70B parameter model. Live evaluation should always be conducted via the `OllamaProvider`.

---

## 4. Legitimate High-Impact Administrative Tasks

- **Challenge**: In administrative or DevOps contexts, a user may genuinely issue a prompt like *"Purge all debug logs in /var/log/system.log"*.
- **Defense Nuance**: While the Intent-Alignment defense correctly recognizes when an action is grounded in the prompt, high-impact side-effect tools (e.g. `rm`, `delete_file`, `bash`) require human-in-the-loop (HITL) confirmation in production environments to avoid irreversible harm from direct prompt injections.
