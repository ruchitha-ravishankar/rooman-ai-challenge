"""Query Analyzer and Sub-Query Decomposition for Research Agent."""

import re
from typing import List, Dict, Any, Optional
from app.config import settings
from app.agent.llm_provider import LLMProvider


class QueryAnalyzer:
    """Analyzes questions, categorizes intent, and decomposes complex queries into targeted search angles."""

    def __init__(self, llm: Optional[LLMProvider] = None):
        self.llm = llm

    def analyze(self, query: str) -> Dict[str, Any]:
        """Analyzes query and produces decomposed sub-queries and intent metadata."""
        cleaned_query = query.strip()
        intent = self._detect_intent(cleaned_query)
        sub_queries = self._decompose(cleaned_query, intent)

        return {
            "original_query": cleaned_query,
            "intent": intent,
            "sub_queries": sub_queries,
            "is_comparison": intent == "comparative",
            "is_multi_hop": len(sub_queries) > 1
        }

    def _detect_intent(self, query: str) -> str:
        """Determines research intent type."""
        q_lower = query.lower()
        if any(w in q_lower for w in ["compare", "versus", "vs", "difference between", "differ from"]):
            return "comparative"
        elif any(w in q_lower for w in ["how to", "mechanism", "workflow", "process", "pipeline"]):
            return "procedural"
        elif any(w in q_lower for w in ["summary", "overview", "synthesize", "explain all", "broad"]):
            return "synthesis"
        elif any(w in q_lower for w in ["what is", "who is", "when did", "how many", "which"]):
            return "factual"
        return "general_inquiry"

    def _decompose(self, query: str, intent: str) -> List[str]:
        """Decomposes a query into multiple focused sub-queries for hybrid search."""
        sub_queries = [query]

        # If LLM is available and not in pure offline mode, we can use it for smart decomposition
        if self.llm and self.llm.provider in ["gemini", "openai", "groq"]:
            try:
                system_prompt = (
                    "You are a search query decomposition engine for academic & technical research.\n"
                    "Given a user query, output up to 3 distinct, concise search queries (one per line) "
                    "that explore different facets/entities needed to answer the question.\n"
                    "Do not include numbering or bullet points. Output only the queries."
                )
                raw = self.llm.generate(
                    prompt=f"Decompose this research question: {query}",
                    system_prompt=system_prompt,
                    temperature=0.1,
                    max_tokens=150
                )
                lines = [line.strip().lstrip('123456789.-* ') for line in raw.strip().splitlines() if line.strip()]
                valid_lines = [l for l in lines if len(l) > 3 and not l.lower().startswith("here are")]
                if valid_lines:
                    return valid_lines[:settings.MAX_SUB_QUERIES]
            except Exception:
                pass

        # Rule-based decomposition fallback
        if intent == "comparative":
            # Split by comparison keywords
            parts = re.split(r'\b(?:vs|versus|and|compared to|difference between)\b', query, flags=re.IGNORECASE)
            parts = [p.strip() for p in parts if len(p.strip()) > 3]
            if len(parts) >= 2:
                sub_queries = [query] + parts[:2]
        elif len(query.split()) > 8:
            # Extract key noun chunks or remove question words
            simplified = re.sub(r'^(what is|how does|why is|explain|describe|tell me about)\s+', '', query, flags=re.IGNORECASE).strip()
            if simplified and simplified.lower() != query.lower():
                sub_queries.append(simplified)

        return list(dict.fromkeys(sub_queries))[:settings.MAX_SUB_QUERIES]
