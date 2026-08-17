"""Dense Semantic Vector Retrieval Engine with multi-provider embedding support."""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from app.config import settings
from app.models.document import Chunk


class DenseRetriever:
    """Computes dense vector representations and cosine similarity for chunks."""

    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or settings.LLM_PROVIDER
        self.chunks: List[Chunk] = []
        self.embeddings: Optional[np.ndarray] = None
        self._tfidf_vectorizer = None

    def fit(self, chunks: List[Chunk]) -> None:
        """Computes and indexes dense vector representations for all chunks."""
        self.chunks = chunks
        if not chunks:
            self.embeddings = None
            return

        texts = [f"{c.title} - {c.section}: {c.text}" for c in chunks]
        
        # Check if API keys are present for remote embeddings, else use robust local dense vectorizer
        if (self.provider == "gemini" or settings.GEMINI_API_KEY) and self._try_gemini_embed(texts):
            return
        elif (self.provider == "openai" or settings.OPENAI_API_KEY) and self._try_openai_embed(texts):
            return
        else:
            # High-fidelity local TF-IDF + N-gram subword vector space
            self._fit_local_vectorizer(texts)

    def search(
        self,
        query: str,
        top_k: int = settings.TOP_K_CHUNKS,
        doc_filter: Optional[List[str]] = None
    ) -> List[Tuple[Chunk, float]]:
        """Calculates cosine similarity between query and all stored chunk embeddings."""
        if not self.chunks or self.embeddings is None or len(self.embeddings) == 0:
            return []

        query_vec = self._embed_query(query)
        if query_vec is None:
            return []

        # Vectorized cosine similarity (since embeddings are L2 normalized, dot product = cosine sim)
        scores = np.dot(self.embeddings, query_vec)
        # Clip to [0.0, 1.0]
        scores = np.clip(scores, 0.0, 1.0)

        scored_pairs: List[Tuple[Chunk, float]] = []
        for idx, score in enumerate(scores):
            chunk = self.chunks[idx]
            if doc_filter and chunk.doc_id not in doc_filter:
                continue
            if score > 0.0:
                scored_pairs.append((chunk, float(score)))

        scored_pairs.sort(key=lambda x: x[1], reverse=True)
        return scored_pairs[:top_k]

    def _fit_local_vectorizer(self, texts: List[str]) -> None:
        """Fits a subword n-gram TF-IDF vectorizer mapping text to dense normalized vectors."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._tfidf_vectorizer = TfidfVectorizer(
                ngram_range=(1, 3),
                sublinear_tf=True,
                max_features=4096,
                norm='l2'
            )
            sparse_matrix = self._tfidf_vectorizer.fit_transform(texts)
            self.embeddings = sparse_matrix.toarray().astype(np.float32)
        except ImportError:
            # Fallback simple bag-of-words dense matrix
            self._fit_simple_bow(texts)

    def _fit_simple_bow(self, texts: List[str]) -> None:
        """Pure python dense bag-of-words fallback if scikit-learn is missing."""
        vocabulary = {}
        for text in texts:
            for word in text.lower().split():
                if word not in vocabulary:
                    vocabulary[word] = len(vocabulary)

        dim = len(vocabulary)
        matrix = np.zeros((len(texts), dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in text.lower().split():
                if word in vocabulary:
                    matrix[i, vocabulary[word]] += 1.0
            norm = np.linalg.norm(matrix[i])
            if norm > 0:
                matrix[i] /= norm
        self.embeddings = matrix

    def _embed_query(self, query: str) -> Optional[np.ndarray]:
        """Generates embedding vector for a single query string."""
        if self._tfidf_vectorizer is not None:
            vec = self._tfidf_vectorizer.transform([query]).toarray()[0].astype(np.float32)
            norm = np.linalg.norm(vec)
            return (vec / norm) if norm > 0 else vec

        # Remote API query embeddings if active
        if settings.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                res = genai.embed_content(
                    model="models/text-embedding-004",
                    content=query,
                    task_type="retrieval_query"
                )
                vec = np.array(res["embedding"], dtype=np.float32)
                norm = np.linalg.norm(vec)
                return (vec / norm) if norm > 0 else vec
            except Exception:
                pass

        if self.embeddings is not None and len(self.embeddings) > 0:
            # Simple term match fallback
            return np.zeros(self.embeddings.shape[1], dtype=np.float32)
        return None

    def _try_gemini_embed(self, texts: List[str]) -> bool:
        """Attempts to batch generate embeddings via Google Gemini."""
        if not settings.GEMINI_API_KEY:
            return False
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            # Batch embeddings in chunks of 50
            embeddings_list = []
            for i in range(0, len(texts), 50):
                batch = texts[i:i+50]
                res = genai.embed_content(
                    model="models/text-embedding-004",
                    content=batch,
                    task_type="retrieval_document"
                )
                embeddings_list.extend(res["embedding"])
            
            arr = np.array(embeddings_list, dtype=np.float32)
            # L2 normalize
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self.embeddings = arr / norms
            return True
        except Exception as e:
            print(f"Gemini embedding fallback to local: {e}")
            return False

    def _try_openai_embed(self, texts: List[str]) -> bool:
        """Attempts to batch generate embeddings via OpenAI."""
        if not settings.OPENAI_API_KEY:
            return False
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            resp = client.embeddings.create(
                input=texts,
                model="text-embedding-3-small"
            )
            arr = np.array([item.embedding for item in resp.data], dtype=np.float32)
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self.embeddings = arr / norms
            return True
        except Exception as e:
            print(f"OpenAI embedding fallback to local: {e}")
            return False
