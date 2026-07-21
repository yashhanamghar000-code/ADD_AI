"""
Single source of configuration truth (replaces the old pattern of every
module calling `os.getenv(...)` directly, which made it impossible to know
what settings existed without grepping the whole codebase).

Everything else in the app receives values FROM this object rather than
reading the environment itself — that's what makes the rest of the code
testable (just construct a Settings() with different values, no env
juggling needed).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str | None = None) -> str | None:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    return int(raw) if raw is not None else default


@dataclass(frozen=True)
class Settings:
    # --- Azure OpenAI / LLM ---
    azure_llm_deployment: str = field(default_factory=lambda: _env(
        "AZURE_LLM_DEPLOYMENT", "Llama-4-Maverick-17B-128E-Instruct-FP8"))
    azure_openai_api_version: str = field(default_factory=lambda: _env(
        "AZURE_OPENAI_API_VERSION", "2024-02-15-preview"))
    azure_api_key: str | None = field(default_factory=lambda: _env("MY_API_KEY"))
    azure_endpoint: str | None = field(default_factory=lambda: _env("AZURE_OPENAI_ENDPOINT"))
    llm_temperature: float = 0.1

    # --- Embeddings / Reranking ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384  # matches BAAI/bge-small-en-v1.5
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- Retrieval tuning ---
    top_k_per_query: int = 15
    final_docs_per_query: int = 6
    max_total_context_docs: int = 18

    # --- Directories ---
    pdf_folder: str = "data"
    bm25_cache_dir: str = "bm25_cache"
    debug_logs_dir: str = "debug_logs"
    temp_upload_dir: str = "./temp_uploads"

    # --- Parsing concurrency ---
    parser_max_workers: int = field(default_factory=lambda: _env_int(
        "PARSER_MAX_WORKERS", max(2, min(3, (os.cpu_count() or 4) - 2))))

    # --- Qdrant ---
    qdrant_url: str | None = field(default_factory=lambda: _env("QDRANT_URL"))
    qdrant_api_key: str | None = field(default_factory=lambda: _env("QDRANT_API_KEY"))
    qdrant_collection_name: str = field(default_factory=lambda: _env(
        "QDRANT_COLLECTION_NAME", "audito_documents"))

    # --- Postgres ---
    database_url: str | None = field(default_factory=lambda: _env("DATABASE_URL"))

    # --- Redis / Celery ---
    redis_url: str = field(default_factory=lambda: _env("REDIS_URL", "redis://localhost:6379/0"))

    # --- Auth / JWT ---
    jwt_secret_key: str | None = field(default_factory=lambda: _env("JWT_SECRET_KEY"))
    jwt_algorithm: str = field(default_factory=lambda: _env("JWT_ALGORITHM", "HS256"))
    jwt_expire_minutes: int = field(default_factory=lambda: _env_int("JWT_EXPIRE_MINUTES", 1440))

    def ensure_directories(self) -> None:
        os.makedirs(self.pdf_folder, exist_ok=True)
        os.makedirs(self.bm25_cache_dir, exist_ok=True)
        os.makedirs(self.debug_logs_dir, exist_ok=True)
        os.makedirs(self.temp_upload_dir, exist_ok=True)


# Process-wide singleton. Every layer that needs configuration takes a
# Settings instance through its constructor (see container.py) rather than
# importing this global directly — the global exists only as the one place
# the composition root reads from.
settings = Settings()
