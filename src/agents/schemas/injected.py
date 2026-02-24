"""
InjectedState — Dependency Injection for LangGraph Nodes

Provides the PageIndexDeps container that is injected into every
LangGraph node via RunnableConfig. This keeps the AgentState lean
(no service references) while giving nodes access to shared services.

Usage in nodes:
    from src.agents.schemas.injected import get_deps

    async def my_node(state: PageIndexQueryState, config: RunnableConfig) -> dict:
        deps = get_deps(config)
        result = await deps.llm.agenerate("prompt")
        await deps.telemetry.log_node_start(...)
        tree = deps.tree_store.load_tree("doc_id")

Usage in orchestrator (injecting deps):
    deps = await create_deps()
    config = {"configurable": {"thread_id": "...", "deps": deps}}
    result = await graph.ainvoke(initial_state, config)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ...observability.logging import get_logger

logger = get_logger(__name__)

# Defer heavy imports to avoid loading PyMuPDF, torch, etc.
# at module import time. Only needed at runtime when create_deps() is called.
if TYPE_CHECKING:
    from ...llm.groq_client import GroqClient
    from ...observability.telemetry import TelemetryService
    from ...pageindex.page_extractor import PageExtractor
    from ...pageindex.tree_store import TreeStore


@dataclass
class PageIndexDeps:
    """
    Dependency container injected into LangGraph nodes.

    Holds shared service instances so nodes don't need to
    instantiate them on every invocation. This is the
    InjectedState pattern — services live in RunnableConfig,
    not in the TypedDict state.

    Attributes:
        llm: Groq LLM client for sync/async generation.
        tree_store: Persistent storage for tree indexes and metadata.
        page_extractor: PDF page content extractor (PyMuPDF).
        telemetry: Async SQLite telemetry service for logging.
        query_id: Current query's telemetry tracking ID.
    """

    llm: GroqClient
    tree_store: TreeStore
    page_extractor: PageExtractor
    telemetry: TelemetryService
    query_id: Optional[str] = field(default=None)


async def create_deps(query_id: Optional[str] = None) -> PageIndexDeps:
    """
    Factory function to create a fully initialized PageIndexDeps.

    Instantiates all services and ensures the telemetry database
    is initialized before returning.

    Args:
        query_id: Telemetry query UUID for the current request.

    Returns:
        Initialized PageIndexDeps with all services ready.

    Raises:
        ValueError: If GROQ_API_KEY is not set (from GroqClient).
    """
    # Lazy imports at runtime — avoids loading PyMuPDF etc. at module level
    from ...llm.groq_client import GroqClient
    from ...observability.telemetry import get_telemetry_service
    from ...pageindex.page_extractor import PageExtractor
    from ...pageindex.tree_store import TreeStore

    telemetry = await get_telemetry_service()

    deps = PageIndexDeps(
        llm=GroqClient(),
        tree_store=TreeStore(),
        page_extractor=PageExtractor(),
        telemetry=telemetry,
        query_id=query_id,
    )

    logger.info(
        "injected.deps_created",
        query_id=query_id,
        has_llm=True,
        has_tree_store=True,
        has_page_extractor=True,
        has_telemetry=True,
    )

    return deps


def get_deps(config: dict) -> PageIndexDeps:
    """
    Extract PageIndexDeps from a LangGraph RunnableConfig.

    This is the primary way nodes access injected services.

    Args:
        config: The RunnableConfig dict passed to every node.

    Returns:
        PageIndexDeps instance from the config.

    Raises:
        KeyError: If deps are not found in the config.
        TypeError: If deps is not a PageIndexDeps instance.
    """
    configurable = config.get("configurable", {})
    deps = configurable.get("deps")

    if deps is None:
        raise KeyError(
            "PageIndexDeps not found in RunnableConfig. "
            "Ensure 'deps' is set in config['configurable'] when invoking the graph."
        )

    if not isinstance(deps, PageIndexDeps):
        raise TypeError(
            f"Expected PageIndexDeps, got {type(deps).__name__}. "
            f"Ensure create_deps() is used to build the deps object."
        )

    return deps
