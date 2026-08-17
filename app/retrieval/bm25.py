"""BM25 (Best Matching 25) Sparse Keyword Retrieval Engine."""

import re
import math
from typing import List, Dict, Tuple, Optional
from app.config import settings
from app.models.document import Chunk, ScoredChunk

# Minimal English stop words list for clean keyword extraction
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't",
    "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself",
    "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into",
    "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's",
    "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs",
    "them", "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's",
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't",
    "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself",
    "yourselves"
}


def tokenize(text: str) -> List[str]:
    """Tokenizes text into normalized lowercase alphanumeric tokens, filtering stop words."""
    words = re.findall(r'[a-zA-Z0-9_-]+', text.lower())
    return [w for w in words if len(w) > 1 and w not in STOP_WORDS]


class BM25Retriever:
    """BM25Okapi implementation with optional rank-bm25 or high-performance native fallback."""

    def __init__(self, k1: float = settings.BM25_K1, b: float = settings.BM25_B):
        self.k1 = k1
        self.b = b
        self.chunks: List[Chunk] = []
        self.corpus_size: int = 0
        self.avg_doc_len: float = 0.0
        self.doc_lens: List[int] = []
        self.doc_freqs: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.tokenized_corpus: List[List[str]] = []
        self._rank_bm25_model = None

    def fit(self, chunks: List[Chunk]) -> None:
        """Indexes a list of chunks into the BM25 inverted index."""
        self.chunks = chunks
        self.corpus_size = len(chunks)
        if self.corpus_size == 0:
            return

        self.tokenized_corpus = [tokenize(f"{c.title} {c.section} {c.text}") for c in chunks]
        self.doc_lens = [len(doc) for doc in self.tokenized_corpus]
        self.avg_doc_len = sum(self.doc_lens) / max(1, self.corpus_size)

        # Compute document frequencies
        self.doc_freqs = {}
        for doc in self.tokenized_corpus:
            unique_terms = set(doc)
            for term in unique_terms:
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        # Calculate inverse document frequency (IDF) with standard BM25 smoothing
        self.idf = {}
        for term, freq in self.doc_freqs.items():
            self.idf[term] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

        # Try initializing rank_bm25 if installed
        try:
            from rank_bm25 import BM25Okapi
            self._rank_bm25_model = BM25Okapi(self.tokenized_corpus, k1=self.k1, b=self.b)
        except ImportError:
            self._rank_bm25_model = None

    def search(
        self,
        query: str,
        top_k: int = settings.TOP_K_CHUNKS,
        doc_filter: Optional[List[str]] = None
    ) -> List[Tuple[Chunk, float]]:
        """Scores all chunks against the query and returns top_k results."""
        if not self.chunks or self.corpus_size == 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        # Use rank_bm25 if available, else native calculation
        if self._rank_bm25_model is not None:
            scores = self._rank_bm25_model.get_scores(query_tokens)
        else:
            scores = [self._score_single_doc(query_tokens, idx) for idx in range(self.corpus_size)]

        # Pair with chunks and filter
        scored_pairs: List[Tuple[Chunk, float]] = []
        for idx, score in enumerate(scores):
            chunk = self.chunks[idx]
            if doc_filter and chunk.doc_id not in doc_filter:
                continue
            if score > 0.0:
                scored_pairs.append((chunk, float(score)))

        # Sort descending by BM25 score
        scored_pairs.sort(key=lambda x: x[1], reverse=True)
        return scored_pairs[:top_k]

    def _score_single_doc(self, query_tokens: List[str], doc_idx: int) -> float:
        """Native BM25 scoring for a single document index."""
        doc_tokens = self.tokenized_corpus[doc_idx]
        doc_len = self.doc_lens[doc_idx]
        
        # Term counts in document
        term_counts: Dict[str, int] = {}
        for t in doc_tokens:
            term_counts[t] = term_counts.get(t, 0) + 1

        score = 0.0
        for token in query_tokens:
            if token not in term_counts:
                continue
            tf = term_counts[token]
            idf = self.idf.get(token, 0.1)
            
            numerator = tf * (self.k1 + 1.0)
            denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / max(1.0, self.avg_doc_len)))
            score += idf * (numerator / denominator)

        return score
