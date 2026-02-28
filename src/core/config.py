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

    # ─────────────────────────────────────────────
    # Convex Backend (Stateless Storage)
    # ─────────────────────────────────────────────
    convex_url: str = Field(
        default="http://localhost:3210",  # Default local convex dev
        alias="CONVEX_URL",
        description="Convex remote database URL",
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
    # Agent
    # ─────────────────────────────────────────────
    max_retries: int = 3

    # ─────────────────────────────────────────────
    # Observability
    # ─────────────────────────────────────────────
    otlp_endpoint: Optional[str] = Field(default=None, alias="OTLP_ENDPOINT")
    prometheus_port: int = 9090

    # ─────────────────────────────────────────────
    # API
    # ─────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8080, alias="PORT")
    allowed_origins_str: str = Field(
        default="http://localhost:3000",
        alias="ALLOWED_ORIGINS",
        description=(
            "CORS allowed origins as a comma-separated string. "
            "Defaults to localhost:3000 for dev."
        ),
    )

    @property
    def allowed_origins(self) -> list[str]:
        """Parse ALLOWED_ORIGINS from comma-separated string."""
        return [o.strip() for o in self.allowed_origins_str.split(",") if o.strip()]

    # ─── Computed properties ────────────────────

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()
