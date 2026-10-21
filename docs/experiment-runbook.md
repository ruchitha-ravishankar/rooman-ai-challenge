# Experiment Runbook: Reproducing MCP Defense Evaluations

This runbook provides step-by-step instructions for running baseline experiments, evaluating defenses, executing adaptive fuzzing, and launching the interactive dashboard.

---

## 1. Prerequisites & Environment Setup

### 1.1 Python Virtual Environment
Ensure you are using Python 3.10+ (tested on Python 3.14 / 3.15):
```bash
# Activate existing virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 2. Running Offline Benchmark Evaluations

The framework runs 100% offline out-of-the-box using the deterministic mock provider.

### 2.1 Full Multi-Defense Benchmark
Run all 5 defenses against the 40-case synthetic benchmark suite:
```bash
python cli.py run-experiment --defense all --cases 40
```

### 2.2 Evaluating a Specific Defense Strategy
Run an evaluation for the novel Intent-Alignment defense:
```bash
python cli.py run-experiment --defense intent_alignment_defense --cases 40
```

Available defense keys:
- `no_defense_baseline` (Audit baseline)
- `keyword_rule_scanner` (Regex keyword filter)
- `llm_judge_scanner` (Secondary judge)
- `schema_pinning_and_rbac` (Cryptographic pinning + RBAC)
- `intent_alignment_defense` (Novel semantic intent defense)

### 2.3 Inspecting Persisted Results in SQLite
View the persisted experiment summary table:
```bash
python cli.py show-results
```

---

## 3. Running Bounded Adaptive Fuzzing

Evaluate how defenses hold up under adversarial mutation (synonym substitutions, unicode zero-width insertions, benign wrappers, path obfuscations):
```bash
python cli.py run-fuzz --defense intent_alignment_defense --mutations 2 --cases 20 --seed 42
```

---

## 4. Launching the Interactive Research Dashboard

Launch the local Streamlit dashboard to explore KPI metric cards, comparative trade-off plots, latency profiles, and per-case audit trails:
```bash
streamlit run mcp_defense_lab/dashboard/app.py
```
The dashboard opens automatically in your browser at `http://localhost:8501`.

---

## 5. Launching the REST API

Start the FastAPI server:
```bash
uvicorn mcp_defense_lab.api.app:app --host 127.0.0.1 --port 8000 --reload
```
Interactive API documentation (Swagger UI) is accessible at `http://127.0.0.1:8000/docs`.

---

## 6. Running with a Real Local LLM (Ollama)

To evaluate a real local foundation model instead of the offline scripted provider:

1. Ensure Ollama is installed and running:
   ```bash
   ollama serve
   ```
2. Pull a target model (e.g. Llama 3.2):
   ```bash
   ollama pull llama3.2
   ```
3. Run the evaluation specifying the `ollama` provider:
   ```bash
   python cli.py run-experiment --defense intent_alignment_defense --provider ollama --model llama3.2 --cases 20
   ```

---

## 7. Automated Test Suite

Run the complete test suite (Unit, Integration, Security, and Sandboxing tests):
```bash
pytest tests/ -v
```
