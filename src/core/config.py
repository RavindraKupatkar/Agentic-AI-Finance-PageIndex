"""
Application Configuration - Environment-based settings

Uses Pydantic Settings for type-safe configuration.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings can be overridden via environment variables.
    """
    
    # ─────────────────────────────────────────────
    # Application
    # ─────────────────────────────────────────────
    service_name: str = "finance-agentic-rag"
    environment: str = Field(default="development", alias="ENV")
    log_level: str = "INFO"
    debug: bool = False
    
    # ─────────────────────────────────────────────
    # LLM (Groq)
    # ─────────────────────────────────────────────
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    default_llm_model: str = "llama-3.3-70b-versatile"
    fast_llm_model: str = "llama-3.1-8b-instant"
    
    # ─────────────────────────────────────────────
    # Embeddings
    # ─────────────────────────────────────────────
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_dimension: int = 768
    use_gpu: bool = False
    
    # ─────────────────────────────────────────────
    # Reranker
    # ─────────────────────────────────────────────
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # ─────────────────────────────────────────────
    # Vector Store (Qdrant)
    # ─────────────────────────────────────────────
    qdrant_url: Optional[str] = Field(default=None, alias="QDRANT_URL")
    qdrant_api_key: Optional[str] = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_path: str = "./qdrant_data"  # For local embedded mode
    collection_name: str = "finance_docs"
    
    # ─────────────────────────────────────────────
    # Chunking
    # ─────────────────────────────────────────────
    chunk_size: int = 512
    chunk_overlap: int = 50
    
    # ─────────────────────────────────────────────
    # Retrieval
    # ─────────────────────────────────────────────
    retrieval_top_k: int = 20
    rerank_top_k: int = 5
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
    
    # ─────────────────────────────────────────────
    # API
    # ─────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()
