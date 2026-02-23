"""
LangGraph Flow — PageIndex Query & Ingestion Graphs

This file defines and wires the complete LangGraph state machines
for the PageIndex Finance RAG system.

Two graphs:
    1. QUERY GRAPH:     question → guardrail → router → doc_selector →
                        tree_search → page_retrieve → critic → generator
    2. INGESTION GRAPH: pdf → validate → extract → generate_tree → store

Both graphs use:
    - PageIndexQueryState / PageIndexIngestionState (from state.py)
    - InjectedState pattern (deps via RunnableConfig)
    - Async node functions (from nodes/)
    - Full telemetry logging (via TelemetryService)
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import StateGraph, END

from src.agents.schemas.state import (
    PageIndexQueryState,
    PageIndexIngestionState,
    create_initial_query_state,
    create_initial_ingestion_state,
)

# ─── Query nodes ───────────────────────────────────────
from src.agents.nodes.guardrail_node import (
    validate_input,
    validate_output,
    create_error_response,
)
from src.agents.nodes.router_node import classify_query
from src.agents.nodes.doc_selector_node import select_documents
from src.agents.nodes.tree_search_node import tree_search
from src.agents.nodes.page_retrieve_node import retrieve_pages
from src.agents.nodes.critic_node import evaluate_retrieval
from src.agents.nodes.generator_node import generate_response, generate_response_fast
from src.agents.nodes.planner_node import create_plan

# ─── Ingestion nodes ──────────────────────────────────
from src.agents.nodes.ingestion_nodes import (
    validate_document,
    extract_pdf_metadata,
    generate_tree_index,
    store_tree,
    ingestion_error,
)


# ═══════════════════════════════════════════════════════════
# CONDITIONAL EDGE FUNCTIONS — Query Graph
# ═══════════════════════════════════════════════════════════


def check_input_valid(state: PageIndexQueryState) -> Literal["valid", "invalid"]:
    """Route based on input validation."""
    return "valid" if state.get("input_valid", True) else "invalid"


def route_by_complexity(state: PageIndexQueryState) -> str:
    """Route based on query complexity classification."""
    query_type = state.get("query_type", "standard")
    if query_type == "simple":
        return "simple"
    elif query_type in ("complex", "multi_hop"):
        return "complex"
    return "standard"


def should_retry(state: PageIndexQueryState) -> Literal["retry", "proceed"]:
    """Check if critic recommends retrying tree search."""
    return "retry" if state.get("needs_retry", False) else "proceed"


# ═══════════════════════════════════════════════════════════
# CONDITIONAL EDGE FUNCTION — Ingestion Graph
# ═══════════════════════════════════════════════════════════


def check_document_valid(state: PageIndexIngestionState) -> Literal["valid", "invalid"]:
    """Route based on document validation result."""
    return "valid" if state.get("is_valid", False) else "invalid"


# ═══════════════════════════════════════════════════════════
# QUERY GRAPH BUILDER
# ═══════════════════════════════════════════════════════════


def build_query_graph(checkpointer=None) -> StateGraph:
    """
    Build the complete PageIndex query processing graph.

    Flow:
        input_guard → [valid?]
            → YES → router → [complexity?]
                → SIMPLE:  doc_selector → tree_search → page_retrieve → fast_generator → output_guard
                → STANDARD: doc_selector → tree_search → page_retrieve → critic → [retry?] → generator → output_guard
                → COMPLEX:  planner → doc_selector → tree_search → page_retrieve → critic → [retry?] → generator → output_guard
            → NO → error_response → END

    Args:
        checkpointer: Optional memory checkpointer for conversation persistence.

    Returns:
        Compiled StateGraph ready for invoke/ainvoke.
    """
    graph = StateGraph(PageIndexQueryState)

    # ─── Add nodes ─────────────────────────────────────
    graph.add_node("input_guard", validate_input)
    graph.add_node("error_response", create_error_response)
    graph.add_node("router", classify_query)
    graph.add_node("planner", create_plan)
    graph.add_node("doc_selector", select_documents)
    graph.add_node("tree_search", tree_search)
    graph.add_node("page_retrieve", retrieve_pages)
    graph.add_node("critic", evaluate_retrieval)
    graph.add_node("generator", generate_response)
    graph.add_node("fast_generator", generate_response_fast)
    graph.add_node("output_guard", validate_output)

    # ─── Entry point ───────────────────────────────────
    graph.set_entry_point("input_guard")

    # ─── Conditional: input valid? ─────────────────────
    graph.add_conditional_edges(
        "input_guard",
        check_input_valid,
        {"valid": "router", "invalid": "error_response"},
    )
    graph.add_edge("error_response", END)

    # ─── Conditional: route by complexity ──────────────
    graph.add_conditional_edges(
        "router",
        route_by_complexity,
        {
            "simple": "doc_selector",
            "standard": "doc_selector",
            "complex": "planner",
        },
    )

    # ─── Complex path: planner → doc_selector ──────────
    graph.add_edge("planner", "doc_selector")

    # ─── All paths: doc_selector → tree_search → page_retrieve
    graph.add_edge("doc_selector", "tree_search")
    graph.add_edge("tree_search", "page_retrieve")

    # ─── Simple path: page_retrieve → fast_generator ───
    # (We use a conditional edge on page_retrieve to split simple vs standard/complex)
    def route_after_retrieve(state: PageIndexQueryState) -> str:
        if state.get("query_type") == "simple":
            return "fast_generate"
        return "evaluate"

    graph.add_conditional_edges(
        "page_retrieve",
        route_after_retrieve,
        {"fast_generate": "fast_generator", "evaluate": "critic"},
    )

    graph.add_edge("fast_generator", "output_guard")

    # ─── Standard/Complex: critic → [retry?] → generator
    graph.add_conditional_edges(
        "critic",
        should_retry,
        {"retry": "tree_search", "proceed": "generator"},
    )
    graph.add_edge("generator", "output_guard")

    # ─── Output guard → END ────────────────────────────
    graph.add_edge("output_guard", END)

    # ─── Compile ───────────────────────────────────────
    compiled = graph.compile(checkpointer=checkpointer)
    return compiled


# ═══════════════════════════════════════════════════════════
# INGESTION GRAPH BUILDER
# ═══════════════════════════════════════════════════════════


def build_ingestion_graph() -> StateGraph:
    """
    Build the PageIndex document ingestion graph.

    Flow:
        validate → [valid?]
            → YES → extract → generate_tree → store → END
            → NO  → ingestion_error → END

    Returns:
        Compiled StateGraph for document ingestion.
    """
    graph = StateGraph(PageIndexIngestionState)

    # ─── Add nodes ─────────────────────────────────────
    graph.add_node("validate", validate_document)
    graph.add_node("extract", extract_pdf_metadata)
    graph.add_node("generate_tree", generate_tree_index)
    graph.add_node("store", store_tree)
    graph.add_node("ingestion_error", ingestion_error)

    # ─── Entry point ───────────────────────────────────
    graph.set_entry_point("validate")

    # ─── Conditional: valid? ───────────────────────────
    graph.add_conditional_edges(
        "validate",
        check_document_valid,
        {"valid": "extract", "invalid": "ingestion_error"},
    )

    # ─── Check after extract (may fail page limit) ─────
    graph.add_conditional_edges(
        "extract",
        check_document_valid,
        {"valid": "generate_tree", "invalid": "ingestion_error"},
    )

    graph.add_edge("generate_tree", "store")
    graph.add_edge("store", END)
    graph.add_edge("ingestion_error", END)

    # ─── Compile ───────────────────────────────────────
    compiled = graph.compile()
    return compiled


# ═══════════════════════════════════════════════════════════
# FACTORY — Cached graph instances
# ═══════════════════════════════════════════════════════════

_query_graph = None
_ingestion_graph = None


def get_query_graph(checkpointer=None):
    """Get or create the query graph (cached singleton)."""
    global _query_graph
    if _query_graph is None:
        _query_graph = build_query_graph(checkpointer)
    return _query_graph


def get_ingestion_graph():
    """Get or create the ingestion graph (cached singleton)."""
    global _ingestion_graph
    if _ingestion_graph is None:
        _ingestion_graph = build_ingestion_graph()
    return _ingestion_graph
