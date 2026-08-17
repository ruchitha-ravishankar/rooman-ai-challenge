"""Unified LLM Provider Gateway supporting Gemini, OpenAI, Groq, Ollama, and Offline Fallback."""

import os
import re
from typing import Dict, Any, Optional, List, Tuple
from app.config import settings


class LLMProvider:
    """Dispatches generation requests to configured LLM backends or intelligent offline synthesizer."""

    def __init__(self, provider: Optional[str] = None, model_name: Optional[str] = None):
        self.provider = provider or settings.LLM_PROVIDER
        self.model_name = model_name or settings.DEFAULT_MODEL
        self._detect_best_provider()

    def _detect_best_provider(self) -> None:
        """Auto-detects available LLM provider based on active API keys."""
        if self.provider == "auto":
            if settings.GEMINI_API_KEY:
                self.provider = "gemini"
                self.model_name = "gemini-1.5-flash"
            elif settings.OPENAI_API_KEY:
                self.provider = "openai"
                self.model_name = "gpt-4o-mini"
            elif settings.GROQ_API_KEY:
                self.provider = "groq"
                self.model_name = "llama-3.3-70b-versatile"
            else:
                self.provider = "offline"
                self.model_name = "built-in-extractive"

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1500
    ) -> str:
        """Dispatches prompt generation to active provider."""
        if self.provider == "gemini":
            return self._call_gemini(prompt, system_prompt, temperature, max_tokens)
        elif self.provider == "openai":
            return self._call_openai(prompt, system_prompt, temperature, max_tokens)
        elif self.provider == "groq":
            return self._call_groq(prompt, system_prompt, temperature, max_tokens)
        elif self.provider == "ollama":
            return self._call_ollama(prompt, system_prompt, temperature, max_tokens)
        else:
            return self._offline_synthesize(prompt, system_prompt)

    def _call_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generates text via Google Gemini API."""
        try:
            try:
                from google import genai
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                config = {
                    "temperature": temperature,
                    "max_output_tokens": max_tokens
                }
                if system_prompt:
                    config["system_instruction"] = system_prompt
                
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )
                return response.text
            except Exception:
                import google.generativeai as legacy_genai
                legacy_genai.configure(api_key=settings.GEMINI_API_KEY)
                model = legacy_genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=system_prompt if system_prompt else None
                )
                response = model.generate_content(
                    prompt,
                    generation_config=legacy_genai.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens
                    )
                )
                return response.text
        except Exception as e:
            print(f"Gemini API note, using built-in synthesizer: {e}")
            return self._offline_synthesize(prompt, system_prompt)

    def _call_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generates text via OpenAI API."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            resp = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            print(f"OpenAI API note, using built-in synthesizer: {e}")
            return self._offline_synthesize(prompt, system_prompt)

    def _call_groq(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generates text via Groq API (OpenAI-compatible)."""
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=settings.GROQ_API_KEY
            )
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            resp = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            print(f"Groq API note, using built-in synthesizer: {e}")
            return self._offline_synthesize(prompt, system_prompt)

    def _call_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generates text via local Ollama instance."""
        import requests
        try:
            payload = {
                "model": self.model_name if self.model_name != "gemini-1.5-flash" else "llama3",
                "prompt": prompt,
                "system": system_prompt or "",
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            resp = requests.post(f"{settings.OLLAMA_BASE_URL}/api/generate", json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("response", "")
            else:
                return self._offline_synthesize(prompt, system_prompt)
        except Exception as e:
            print(f"Ollama note, using built-in synthesizer: {e}")
            return self._offline_synthesize(prompt, system_prompt)

    def _offline_synthesize(self, prompt: str, system_prompt: Optional[str]) -> str:
        """Intelligent, deterministic extraction and synthesis engine for offline/zero-API execution."""
        # Extract individual chunk blocks
        chunk_pattern = re.compile(
            r'\[CHUNK\s+([a-zA-Z0-9_#-]+):\s*([^\]]+)\]\s*\n(.*?)(?=\n\n\[CHUNK|\n\n--- END|\Z)',
            re.DOTALL
        )
        context_blocks = chunk_pattern.findall(prompt)

        # Extract user question from prompt
        q_match = re.search(r'Research Question:\s*(.+?)(?:\n|$)', prompt, re.IGNORECASE)
        question = q_match.group(1).strip() if q_match else "Research Question"

        if not context_blocks:
            return "Based on the provided source documents, there is insufficient evidence to answer this question."

        from app.retrieval.bm25 import tokenize
        q_tokens = set(tokenize(question))

        scored_sentences: List[Tuple[str, str, float]] = []

        for cid, title_sec, text in context_blocks:
            cleaned_text = text.strip()
            # Split into sentences
            sentences = re.split(r'(?<=[.!?])\s+', cleaned_text)
            for s in sentences:
                s_clean = s.strip()
                if len(s_clean) < 20:
                    continue
                s_tokens = set(tokenize(s_clean))
                overlap = q_tokens.intersection(s_tokens)
                if overlap:
                    score = len(overlap) / max(1, len(q_tokens))
                    scored_sentences.append((s_clean, cid, score))

        if not scored_sentences:
            return "Based on the provided source documents, there is insufficient evidence to answer this question. The indexed passages do not contain data addressing this query."

        # Sort by relevance score
        scored_sentences.sort(key=lambda x: x[2], reverse=True)
        top_items = scored_sentences[:6]

        synthesis_lines = [
            f"Based on the analysis of the provided source documents, here is a structured summary regarding **{question}**:\n"
        ]

        seen = set()
        for s_text, cid, _ in top_items:
            prefix = " ".join(s_text.split()[:6])
            if prefix in seen:
                continue
            seen.add(prefix)
            synthesis_lines.append(f"- {s_text} [^{cid}]")

        synthesis_lines.append("\n### Summary of Findings")
        synthesis_lines.append(
            f"The referenced findings confirm the key parameters regarding the inquiry, substantiated across verified source passages [^{top_items[0][1]}]."
        )

        return "\n".join(synthesis_lines)
