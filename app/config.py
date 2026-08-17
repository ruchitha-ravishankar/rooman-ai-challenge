"""Configuration settings for VeriCite AI Research Agent."""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SOURCES_DIR = DATA_DIR / "sources"
INDEX_DIR = DATA_DIR / "index"
DOCS_DIR = BASE_DIR / "docs"

# Ensure data directories exist
DATA_DIR.mkdir(exist_ok=True)
SOURCES_DIR.mkdir(exist_ok=True)
INDEX_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    """Application settings and hyperparameter defaults."""
    
    # Environment & Server
    APP_NAME: str = "VeriCite AI Research Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Model Provider Settings
    # Supports: "gemini", "openai", "groq", "ollama", "mock" (offline fallback)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gemini-1.5-flash")
    
    # API Keys
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # Chunking Hyperparameters
    CHUNK_SIZE: int = 650          # Target character length per chunk
    CHUNK_OVERLAP: int = 120       # Overlap between consecutive chunks
    MIN_CHUNK_LENGTH: int = 80     # Discard snippets shorter than this
    
    # Retrieval Hyperparameters
    TOP_K_CHUNKS: int = 5          # Number of chunks passed to synthesizer
    BM25_K1: float = 1.5           # BM25 term frequency saturation parameter
    BM25_B: float = 0.75           # BM25 document length normalization parameter
    HYBRID_ALPHA: float = 0.5      # Weight between BM25 (1 - alpha) and Dense (alpha)
    RRF_K: int = 60                # Reciprocal Rank Fusion smoothing constant
    
    # Verification & Grounding Thresholds
    MIN_RELEVANCE_THRESHOLD: float = 0.18   # Below this, declare insufficient evidence
    VERIFICATION_PASS_THRESHOLD: float = 0.70 # Claim grounding confidence threshold
    MAX_SUB_QUERIES: int = 3       # Max decomposed search angles
    
    model_config = SettingsConfigDict(env_file=".env", extra="allow")


settings = Settings()
