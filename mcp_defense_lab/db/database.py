"""SQLite database connection and table initialization for MCP Defense Lab."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Generator
from mcp_defense_lab.config import settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    defense_name TEXT NOT NULL,
    model_provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    total_cases INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS case_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    title TEXT NOT NULL,
    user_prompt TEXT NOT NULL,
    is_attack INTEGER NOT NULL,
    paradigm TEXT NOT NULL,
    risk_category TEXT NOT NULL,
    proposal_tool TEXT,
    proposal_args_json TEXT,
    proposal_valid INTEGER NOT NULL,
    proposal_latency_ms REAL NOT NULL,
    defense_decision TEXT NOT NULL,
    defense_reason_code TEXT NOT NULL,
    defense_explanation TEXT NOT NULL,
    defense_latency_ms REAL NOT NULL,
    executed INTEGER NOT NULL,
    attack_succeeded INTEGER NOT NULL,
    benign_completed INTEGER NOT NULL,
    total_latency_ms REAL NOT NULL,
    FOREIGN KEY(experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS experiment_reports (
    experiment_id TEXT PRIMARY KEY,
    asr REAL NOT NULL,
    asr_lower REAL NOT NULL,
    asr_upper REAL NOT NULL,
    tcr REAL NOT NULL,
    tcr_lower REAL NOT NULL,
    tcr_upper REAL NOT NULL,
    fpr REAL NOT NULL,
    dbr REAL NOT NULL,
    median_latency_ms REAL NOT NULL,
    p95_latency_ms REAL NOT NULL,
    report_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fuzz_runs (
    id TEXT PRIMARY KEY,
    defense_name TEXT NOT NULL,
    seed INTEGER NOT NULL,
    mutations_count INTEGER NOT NULL,
    delta_asr REAL NOT NULL,
    delta_tcr REAL NOT NULL,
    delta_fpr REAL NOT NULL,
    summary TEXT NOT NULL,
    full_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class DatabaseManager:
    """Manages SQLite database connections and table lifecycle."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or settings.DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Return a configured SQLite connection with foreign keys and row factory."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_schema(self) -> None:
        """Initialize database tables if they do not exist."""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()


db = DatabaseManager()
