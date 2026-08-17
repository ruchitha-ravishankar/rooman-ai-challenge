"""Citation-Grounded Synthesis Engine for Research Agent."""

import re
from typing import List, Dict, Any, Optional
from app.config import settings
from app.models.document import ScoredChunk
from app.agent.llm_provider import LLMProvider


SYNTHESIS_SYSTEM_PROMPT = """You are VeriCite AI, an elite academic and technical research agent designed for high-integrity synthesis with strict citation grounding.

YOUR CORE MANDATE:
1. Ground every single assertion in the provided source passages.
2. Every factual statement or claim MUST end with an explicit citation tag pointing to the exact chunk ID it was derived from, formatted as `[^CHUNK_ID]`. Example: "Quantum dots improve optical contrast by 40% [^quantum_comp#c003]."
3. If multiple passages support a claim, cite all relevant chunks: "[^doc1#c001][^doc2#c004]".
4. DO NOT invent citations or cite chunk IDs that are not explicitly provided in the context.
5. If the provided sources DO NOT contain sufficient evidence to answer the user's question, you MUST clearly state:
   "Based on the provided source documents, there is insufficient evidence to answer this question."
   Do NOT attempt to speculate, use outside knowledge, or hallucinate an answer when the source passages lack evidence.
6. Provide a well-structured, clear markdown answer with headings and bullet points where appropriate.
"""


class Synthesizer:
    """Generates grounded research summaries with granular citation anchors."""

    def __init__(self, llm: Optional[LLMProvider] = None):
        self.llm = llm or LLMProvider()

    def synthesize(
        self,
        query: str,
        context_chunks: List[ScoredChunk],
        strict_citations: bool = True
    ) -> str:
        """Synthesizes an answer grounded in the retrieved chunks with citation tags."""
        if not context_chunks:
            return "Based on the provided source documents, there is insufficient evidence to answer this question. No relevant source passages were found in the index."

        # Format context passages with explicit chunk tags
        context_blocks = []
        for scored in context_chunks:
            c = scored.chunk
            header = f"[CHUNK {c.chunk_id}: {c.title} - {c.section}]"
            body = c.text.strip()
            context_blocks.append(f"{header}\n{body}")

        formatted_context = "\n\n".join(context_blocks)

        user_prompt = (
            f"Research Question: {query}\n\n"
            f"--- SOURCE PASSAGES ---\n"
            f"{formatted_context}\n"
            f"--- END SOURCE PASSAGES ---\n\n"
            f"Please synthesize a rigorous, comprehensive answer to the research question strictly using the source passages above. "
            f"Attach citation tags `[^CHUNK_ID]` to each specific claim. If the passages do not contain the answer, explicitly state that there is insufficient evidence."
        )

        answer = self.llm.generate(
            prompt=user_prompt,
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            temperature=0.15,
            max_tokens=1500
        )

        return answer.strip()
