"""Configuration management for MCP Defense Lab."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_DEFENSE_",
        env_file=".env",
        extra="ignore",
    )

    # Base Paths
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    DB_PATH: Path = DATA_DIR / "mcp_defense_lab.db"

    # Evaluation & Randomness
    DEFAULT_SEED: int = 42
    DEFAULT_TIMEOUT_SECONDS: float = 30.0

    # Local LLM Engine (Ollama)
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_DEFAULT_MODEL: str = "llama3.2"
    OLLAMA_REQUEST_TIMEOUT: float = 45.0

    # API Server
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000

    # Dashboard
    DASHBOARD_PORT: int = 8501

    # Safe Simulator Safeguards
    SIMULATOR_MAX_FILE_BYTES: int = 10 * 1024 * 1024  # 10 MB limit
    SIMULATOR_MAX_COMMAND_OUTPUT_LINES: int = 200

    # Defense Defaults
    INTENT_ALIGNMENT_STRICTNESS: float = 0.75
    KEYWORD_SCANNER_CASE_INSENSITIVE: bool = True


settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
