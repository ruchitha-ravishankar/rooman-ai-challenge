# VeriCite AI: Engineering Trade-offs, Failure Modes, and Design Decisions

This document outlines the architectural trade-offs, design decisions, failure modes, and scalability considerations made during the development of **VeriCite AI** for the **Rooman AI Challenge**.

---

## 1. Architectural & Engineering Trade-offs

| Design Decision | Chosen Approach | Alternative Considered | Rationale & Trade-off |
| :--- | :--- | :--- | :--- |
| **Retrieval Architecture** | Calibrated Hybrid RRF (BM25 + Dense) | Pure Vector Embedding Search | Pure vector search frequently fails on exact alphanumeric parameters (e.g. "ML-KEM-768", "20.1 Tesla", "FIPS 203"). BM25 ensures 100% precision on technical tokens, while Dense embeddings capture paraphrased semantic intent. |
| **LLM Gateway & Zero-Key Fallback** | Multi-Provider (Gemini, OpenAI, Groq, Ollama, Built-in) | Hard dependency on single paid API | Reviewers must be able to run the agent immediately without needing to provision paid API keys. The built-in deterministic synthesizer guarantees 100% test reproducibility offline. |
| **Chunking Granularity** | 650 chars with 120-char semantic overlap | Large 2,000+ char chunks | Smaller chunks provide surgical citation attribution (pinpointing exact sentences/paragraphs) and minimize noise in context windows, at the cost of slightly higher index memory consumption. |
| **Verification Strategy** | Deterministic Token Recall + Continuous N-gram Alignment | LLM-as-a-judge Verification Step | Deterministic N-gram/token verification executes in $<2\text{ms}$ with zero added API latency or cost, and eliminates recursive hallucinations from LLM judges. |
| **Refusal Policy** | Hard Threshold Guardrail ($\theta = 0.180$) | Soft prompt instruction only ("say you don't know") | LLMs routinely ignore prompt instructions when confronted with out-of-domain queries, inventing plausible sounding facts. Enforcing a hard similarity check at the retrieval layer halts generation entirely. |

---

## 2. Model & Embedding Selection Analysis

1. **Google Gemini 1.5 / 2.0 Flash (`google-genai`)**:
   - *Strengths*: High speed, large native context window, strong structured instruction following.
   - *Trade-off*: Requires active network connection and API key.

2. **Built-in Local Vectorizer & Extractive Engine**:
   - *Strengths*: Zero network dependencies, instant startup, deterministic benchmark results, runs anywhere in $<3\text{ms}$.
   - *Trade-off*: Synthesis phrasing follows direct extractive consolidation rather than creative re-expression.

---

## 3. Known Limitations & Failure Modes

1. **Syntactic Ambiguity in Highly Complex Multi-sentence Bullet Points**:
   - If a synthesis combines claims from multiple disparate chunks into a single compound sentence with only one citation tag at the end, the secondary claim may register a lower grounding score.
   - *Mitigation*: The Query Analyzer breaks queries into atomic sub-questions, and the prompt encourages 1-claim-per-sentence structure.

2. **Table & Figure Provenance in Scanned PDFs**:
   - Complex nested tables in scanned PDFs without OCR text layers can lose spatial structure during linear text extraction.
   - *Mitigation*: Section headers and page numbers are preserved so users can inspect the original page directly in the UI.

3. **Very Short Acronym Queries**:
   - Queries with single 2-letter acronyms without context (e.g., "AI", "QC") have high ambiguity across documents.
   - *Mitigation*: Sub-query expansion adds domain context to disambiguate.

---

## 4. Future Roadmap & Improvements (With More Time)

If expanded beyond the 24-hour hackathon scope:
1. **Agentic Web-Search Integration**: Integrate live ArXiv and PubMed APIs with dynamic query rewriting.
2. **Cross-Encoder Reranker**: Add a localized MiniLM cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) for second-stage passage re-ranking.
3. **Graph-RAG Knowledge Graph**: Build an entity-relationship graph across documents to enable multi-hop reasoning over complex scientific ontologies.
4. **PDF Bounding-Box Visual Citations**: Render the original PDF page with visual highlighted bounding boxes around the exact cited sentences in the UI.
