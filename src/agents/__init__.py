"""
LangGraph Multi-Agent System — PageIndex Finance RAG

Production-grade agentic RAG with:
- PageIndex tree-based retrieval (replaces vector search)
- Multi-hop reasoning via tree navigation
- Self-correction via critic agent
- Async telemetry via SQLite
"""

from .schemas.state import (
    PageIndexQueryState,
    PageIndexIngestionState,
    create_initial_query_state,
    create_initial_ingestion_state,
)

__all__ = [
    "PageIndexQueryState",
    "PageIndexIngestionState",
    "create_initial_query_state",
    "create_initial_ingestion_state",
]
