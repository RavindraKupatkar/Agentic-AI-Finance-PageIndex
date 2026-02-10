"""
Main Query Processing Graph - LangGraph Implementation

This is the core graph that orchestrates the entire RAG pipeline
with multi-agent capabilities and self-correction.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Literal

from ..schemas.state import AgentState
from ..nodes import (
    router_node,
    planner_node,
    retriever_node,
    critic_node,
    generator_node,
    guardrail_node
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONDITIONAL EDGE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def route_by_complexity(state: AgentState) -> Literal["fast_path", "standard", "planner"]:
    """
    Route query based on complexity assessment.
    
    - fast_path: Simple queries → direct retrieval + generation
    - standard: Medium queries → retrieval + critic + generation  
    - planner: Complex queries → plan + multi-step execution
    """
    query_type = state.get("query_type", "standard")
    
    if query_type == "simple":
        return "fast_path"
    elif query_type in ["complex", "multi_hop"]:
        return "planner"
    return "standard"


def should_retry(state: AgentState) -> Literal["retry", "generate"]:
    """
    Decide if we should retry retrieval based on critic evaluation.
    """
    needs_retry = state.get("needs_retry", False)
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if needs_retry and retry_count < max_retries:
        return "retry"
    return "generate"


def check_input_valid(state: AgentState) -> Literal["continue", "reject"]:
    """Check if input passed guardrails"""
    if state.get("input_valid", True):
        return "continue"
    return "reject"


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_query_graph(checkpointer=None) -> StateGraph:
    """
    Build the main query processing StateGraph.
    
    Flow:
        START
          ↓
        input_guard ──→ [reject] ──→ error_response ──→ END
          ↓ [continue]
        router
          ├──→ [fast_path] ──→ retriever ──→ generator ──→ output_guard ──→ END
          ├──→ [standard]  ──→ retriever ──→ critic ──→ generator ──→ output_guard ──→ END
          └──→ [planner]   ──→ planner ──→ retriever ──→ critic ──→ generator ──→ output_guard ──→ END
                                                ↑          │
                                                └── [retry]┘
    
    Args:
        checkpointer: LangGraph checkpointer for conversation memory
        
    Returns:
        Compiled StateGraph
    """
    # Initialize graph with state schema
    builder = StateGraph(AgentState)
    
    # ─────────────────────────────────────────────
    # ADD NODES
    # ─────────────────────────────────────────────
    
    # Guardrails
    builder.add_node("input_guard", guardrail_node.validate_input)
    builder.add_node("output_guard", guardrail_node.validate_output)
    builder.add_node("error_response", guardrail_node.create_error_response)
    
    # Routing & Planning
    builder.add_node("router", router_node.classify_query)
    builder.add_node("planner", planner_node.create_plan)
    
    # Core RAG
    builder.add_node("retriever", retriever_node.retrieve_and_rerank)
    builder.add_node("critic", critic_node.evaluate_retrieval)
    builder.add_node("generator", generator_node.generate_response)
    
    # Fast path (no critic)
    builder.add_node("fast_generator", generator_node.generate_response_fast)
    
    # ─────────────────────────────────────────────
    # DEFINE EDGES
    # ─────────────────────────────────────────────
    
    # Entry: START → input_guard
    builder.add_edge(START, "input_guard")
    
    # Input guard conditional
    builder.add_conditional_edges(
        "input_guard",
        check_input_valid,
        {
            "continue": "router",
            "reject": "error_response"
        }
    )
    
    # Error response → END
    builder.add_edge("error_response", END)
    
    # Router conditional edges
    builder.add_conditional_edges(
        "router",
        route_by_complexity,
        {
            "fast_path": "retriever",
            "standard": "retriever", 
            "planner": "planner"
        }
    )
    
    # Planner → Retriever
    builder.add_edge("planner", "retriever")
    
    # Retriever → Critic (for standard/complex)
    builder.add_edge("retriever", "critic")
    
    # Critic conditional: retry or generate
    builder.add_conditional_edges(
        "critic",
        should_retry,
        {
            "retry": "retriever",
            "generate": "generator"
        }
    )
    
    # Generator → Output Guard
    builder.add_edge("generator", "output_guard")
    builder.add_edge("fast_generator", "output_guard")
    
    # Output Guard → END
    builder.add_edge("output_guard", END)
    
    # ─────────────────────────────────────────────
    # COMPILE
    # ─────────────────────────────────────────────
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    return builder.compile(checkpointer=checkpointer)


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Singleton instance
_query_graph = None


def get_query_graph(persistent: bool = False, db_path: str = "./checkpoints.db"):
    """
    Get or create the query graph singleton.
    
    Args:
        persistent: Use SQLite for persistent memory across restarts
        db_path: Path to SQLite database for persistence
        
    Returns:
        Compiled StateGraph
    """
    global _query_graph
    
    if _query_graph is None:
        if persistent:
            checkpointer = SqliteSaver.from_conn_string(db_path)
        else:
            checkpointer = MemorySaver()
        
        _query_graph = build_query_graph(checkpointer)
    
    return _query_graph


def reset_query_graph():
    """Reset the graph singleton (useful for testing)"""
    global _query_graph
    _query_graph = None
