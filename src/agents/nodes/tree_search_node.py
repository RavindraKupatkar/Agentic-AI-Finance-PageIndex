"""
Tree Search Agent Node — LangGraph Node for PageIndex Tree Search

LangGraph node that wraps the TreeSearcher to perform reasoning-based
retrieval within the query graph.

Replaces the retriever_node.py in the traditional RAG pipeline:
    Vector retrieval node → Tree search agent node

This node:
    1. Loads document trees from state
    2. Runs TreeSearcher for each selected document
    3. Updates the AgentState with search results and reasoning trace
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import time
from typing import TYPE_CHECKING, Any

from ..schemas.state import PageIndexQueryState
from ..schemas.injected import get_deps
from ...observability.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from ...pageindex.tree_searcher import TreeSearcher, SearchResult
    from ...pageindex.tree_generator import DocumentTree

async def tree_search(
    state: PageIndexQueryState, config: RunnableConfig
) -> dict[str, Any]:
    """
    🌲 TREE SEARCH — LLM reasons through tree index to find relevant pages.

    ⭐ KEY NODE — The core PageIndex innovation.

    For each selected document, navigates the tree top-down:
    1. Read root node summaries
    2. LLM reasons: "Which branch likely has the answer?"
    3. Drill into selected branch
    4. Repeat until reaching leaf nodes (exact pages)

    Uses refined_query from critic if on a retry attempt.

    Args:
        state: Current state with question, selected_doc_ids, tree_structures.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with relevant_pages, reasoning_trace, search_confidence, retry_count.
    """
    start_time = time.time()
    deps = get_deps(config)

    # Lazy imports to prevent loading PyMuPDF at module import time
    from ...pageindex.tree_searcher import TreeSearcher, SearchResult
    from ...pageindex.tree_generator import DocumentTree

    # Use refined_query if available (retry from critic), else original question
    query = state.get("refined_query") or state["question"]
    tree_structures = state.get("tree_structures", {})
    selected_doc_ids = state.get("selected_doc_ids", [])
    retry_count = state.get("retry_count", 0)

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="tree_search",
        input_summary={
            "query_length": len(query),
            "doc_count": len(selected_doc_ids),
            "retry_count": retry_count,
        },
    )

    try:
        searcher = TreeSearcher(
            llm=deps.llm,
            telemetry=deps.telemetry,
            query_id=state.get("query_id"),
        )

        all_relevant_pages: dict[str, list[int]] = {}
        all_reasoning: list[dict] = []
        total_confidence = 0.0

        for doc_id in selected_doc_ids:
            tree_data = tree_structures.get(doc_id)
            if not tree_data:
                logger.warning("tree_search.missing_tree", doc_id=doc_id)
                continue

            # Reconstruct DocumentTree from dict
            if isinstance(tree_data, dict):
                tree = DocumentTree.from_dict(tree_data)
            else:
                tree = tree_data

            result: SearchResult = await searcher.search(query=query, tree=tree)

            all_relevant_pages[doc_id] = result.relevant_pages
            all_reasoning.extend([step.to_dict() for step in result.reasoning_trace])
            total_confidence += result.confidence

        # Average confidence across documents
        search_confidence = (
            total_confidence / len(selected_doc_ids)
            if selected_doc_ids
            else 0.0
        )

        duration_ms = (time.time() - start_time) * 1000

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="tree_search",
            output_summary={
                "total_pages_found": sum(len(p) for p in all_relevant_pages.values()),
                "docs_searched": len(selected_doc_ids),
                "confidence": round(search_confidence, 3),
            },
            duration_ms=duration_ms,
        )

        logger.info(
            "tree_search.complete",
            total_pages=sum(len(p) for p in all_relevant_pages.values()),
            confidence=round(search_confidence, 3),
            elapsed_ms=round(duration_ms, 1),
        )

        return {
            "relevant_pages": all_relevant_pages,
            "reasoning_trace": all_reasoning,
            "search_confidence": search_confidence,
            "retry_count": retry_count,
        }

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("tree_search.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="tree_search",
            duration_ms=duration_ms,
            error=str(exc),
        )
        await deps.telemetry.log_error(
            error_type=type(exc).__name__,
            error_message=str(exc),
            query_id=state.get("query_id", ""),
            node_name="tree_search",
            exception=exc,
            recovery_action="return_empty",
        )
        return {
            "relevant_pages": {},
            "reasoning_trace": [],
            "search_confidence": 0.0,
            "retry_count": retry_count,
            "error": f"Tree search failed: {str(exc)}",
        }
