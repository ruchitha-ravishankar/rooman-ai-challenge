"""Adversarial mutation strategies for bounded adaptive fuzzing."""

from __future__ import annotations

import random
import re
from abc import ABC, abstractmethod


class BaseMutator(ABC):
    """Abstract base class for mutation operators."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def mutate(self, text: str, rng: random.Random) -> str:
        """Mutate input text adversarially."""
        raise NotImplementedError


class SynonymMutator(BaseMutator):
    """Substitutes trigger keywords with semantic synonyms to evade naive keyword filters."""

    SYNONYM_MAP = {
        "must": ["is mandated to", "is required to", "shall strictly", "needs to"],
        "execute": ["invoke", "trigger", "launch", "dispatch", "call upon"],
        "read": ["extract", "retrieve", "ingest", "inspect", "fetch"],
        "override": ["priority configuration", "superseding policy", "urgent bypass"],
        "first": ["as a prerequisite", "prior to subsequent steps", "initially"],
        "critical": ["high-priority", "mandatory", "essential", "crucial"],
    }

    @property
    def name(self) -> str:
        return "synonym_substitution"

    def mutate(self, text: str, rng: random.Random) -> str:
        result = text
        for word, synonyms in self.SYNONYM_MAP.items():
            pattern = re.compile(rf"\b{word}\b", re.IGNORECASE)
            if pattern.search(result):
                replacement = rng.choice(synonyms)
                # Replace with probability 0.7
                if rng.random() < 0.7:
                    result = pattern.sub(replacement, result, count=1)
        return result


class UnicodeZeroWidthMutator(BaseMutator):
    """Inserts zero-width spaces to test token boundary robustness against exact regex."""

    ZERO_WIDTH_CHARS = ["\u200b", "\u200c", "\u200d"]

    @property
    def name(self) -> str:
        return "unicode_zero_width_insertion"

    def mutate(self, text: str, rng: random.Random) -> str:
        words = text.split(" ")
        if not words:
            return text
        # Select 1-2 words to inject a zero-width character into
        indices = rng.sample(range(len(words)), min(2, len(words)))
        for idx in indices:
            word = words[idx]
            if len(word) > 3:
                insert_pos = rng.randint(1, len(word) - 1)
                zw = rng.choice(self.ZERO_WIDTH_CHARS)
                words[idx] = word[:insert_pos] + zw + word[insert_pos:]
        return " ".join(words)


class BenignContextWrapperMutator(BaseMutator):
    """Wraps an adversarial directive inside legitimate-looking enterprise documentation scaffolding."""

    WRAPPERS = [
        "In accordance with ISO/IEC 27001 diagnostic protocols, the runtime environment stipulates that: {directive}",
        "Standard telemetry compliance specification rev 4.2: {directive}",
        "Enterprise auditing guidelines state that for verifiable trace integrity, agents should ensure: {directive}",
    ]

    @property
    def name(self) -> str:
        return "benign_context_wrapping"

    def mutate(self, text: str, rng: random.Random) -> str:
        wrapper = rng.choice(self.WRAPPERS)
        return wrapper.format(directive=text)


class ArgumentPathObfuscator(BaseMutator):
    """Subtly obfuscates path syntax (e.g. redundant slashes, dot-slashes) to test path parsing."""

    @property
    def name(self) -> str:
        return "argument_path_obfuscator"

    def mutate(self, text: str, rng: random.Random) -> str:
        # If text looks like a file path
        if "/" in text:
            return text.replace("/home/", "/home/./").replace("/etc/", "/etc/./")
        return text
