"""
Application Configuration - Environment-based settings

Uses Pydantic Settings for type-safe configuration.
Centralized configuration for the PageIndex Finance RAG system.
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


# Project root: two levels up from src/core/config.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables.
    Sensitive values (API keys) MUST come from .env or environment.
    """

    # ─────────────────────────────────────────────
    # Application
    # ─────────────────────────────────────────────
    service_name: str = "finance-agentic-rag"
    environment: str = Field(default="development", alias="ENV")
    log_level: str = "INFO"
    debug: bool = False

    # ─────────────────────────────────────────────
    # LLM (Groq) — All LLM calls go through Groq
    # ─────────────────────────────────────────────
    groq_api_key: Optional[str] = Field(
        default=None,
        alias="GROQ_API_KEY",
        description="Groq API key. Required for all LLM operations.",
    )
    default_llm_model: str = "llama-3.3-70b-versatile"
    fast_llm_model: str = "llama-3.1-8b-instant"

    # ─────────────────────────────────────────────
    # PageIndex — Tree-based RAG (Active Pipeline)
    # ─────────────────────────────────────────────

    # Models
    tree_gen_model: str = Field(
        default="openai/gpt-oss-120b",
        description="Model for tree index generation. Uses Groq OpenAI-compat endpoint.",
    )
    tree_search_model: str = Field(
        default="openai/gpt-oss-120b",
        description="Model for LLM tree search reasoning.",
    )

    # Directories (relative to project root, resolved to absolute)
    pdfs_dir: str = Field(
        default="data/pdfs",
        description="Directory containing source PDF documents.",
    )
    trees_dir: str = Field(
        default="data/trees",
        description="Directory for generated tree index JSON files.",
    )

    # SQLite metadata database
    metadata_db_path: str = Field(
        default="data/pageindex_metadata.db",
        description="Path to SQLite database for document metadata.",
    )

    # Tree generation limits
    max_tree_depth: int = Field(
        default=5,
        ge=2,
        le=10,
        description="Maximum depth of generated tree index.",
    )
    max_pages_per_node: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum pages a single leaf node can reference.",
    )

    # PDF limits (security: prevent abuse)
    max_pdf_size_mb: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum allowed PDF file size in megabytes.",
    )
    max_pdf_pages: int = Field(
        default=1000,
        ge=1,
        le=5000,
        description="Maximum allowed page count per PDF.",
    )

    # Query settings
    max_query_length: int = Field(
        default=2000,
        ge=10,
        le=10000,
        description="Maximum allowed query length in characters.",
    )
    max_search_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum tree search retries when critic rejects results.",
    )
    tree_search_breadth: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum branches to explore per tree level.",
    )

    # ─────────────────────────────────────────────
    # Legacy: Embeddings (DEPRECATED — kept for backward compat)
    # ─────────────────────────────────────────────
    embedding_model: str = "BAAI/bge-base-en-v1.5"  # Unused in PageIndex pipeline
    embedding_dimension: int = 768                    # Unused in PageIndex pipeline
    use_gpu: bool = False

    # ─────────────────────────────────────────────
    # Legacy: Reranker (DEPRECATED — kept for backward compat)
    # ─────────────────────────────────────────────
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # Unused in PageIndex

    # ─────────────────────────────────────────────
    # Legacy: Vector Store / Qdrant (DEPRECATED)
    # ─────────────────────────────────────────────
    qdrant_url: Optional[str] = Field(default=None, alias="QDRANT_URL")
    qdrant_api_key: Optional[str] = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_path: str = "./qdrant_data"
    collection_name: str = "finance_docs"

    # ─────────────────────────────────────────────
    # Legacy: Chunking (DEPRECATED — PageIndex doesn't chunk)
    # ─────────────────────────────────────────────
    chunk_size: int = 512     # Unused in PageIndex pipeline
    chunk_overlap: int = 50   # Unused in PageIndex pipeline

    # ─────────────────────────────────────────────
    # Legacy: Retrieval (DEPRECATED)
    # ─────────────────────────────────────────────
    retrieval_top_k: int = 20        # Unused in PageIndex pipeline
    rerank_top_k: int = 5            # Unused in PageIndex pipeline
    relevance_threshold: float = 0.3

    # ─────────────────────────────────────────────
    # Agent
    # ─────────────────────────────────────────────
    max_retries: int = 3

    # ─────────────────────────────────────────────
    # Observability
    # ─────────────────────────────────────────────
    otlp_endpoint: Optional[str] = Field(default=None, alias="OTLP_ENDPOINT")
    prometheus_port: int = 9090
    telemetry_db_path: str = Field(
        default="data/telemetry.db",
        description="Path to SQLite database for query telemetry and logging.",
    )

    # ─────────────────────────────────────────────
    # API
    # ─────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ─── Computed properties ────────────────────

    @property
    def pdfs_dir_absolute(self) -> Path:
        """Resolve pdfs_dir to absolute path from project root."""
        path = Path(self.pdfs_dir)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return path.resolve()

    @property
    def trees_dir_absolute(self) -> Path:
        """Resolve trees_dir to absolute path from project root."""
        path = Path(self.trees_dir)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return path.resolve()

    @property
    def metadata_db_absolute(self) -> Path:
        """Resolve metadata_db_path to absolute path from project root."""
        path = Path(self.metadata_db_path)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return path.resolve()

    @property
    def telemetry_db_absolute(self) -> Path:
        """Resolve telemetry_db_path to absolute path from project root."""
        path = Path(self.telemetry_db_path)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return path.resolve()

    @property
    def max_pdf_size_bytes(self) -> int:
        """Convert max_pdf_size_mb to bytes for file validation."""
        return self.max_pdf_size_mb * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()
