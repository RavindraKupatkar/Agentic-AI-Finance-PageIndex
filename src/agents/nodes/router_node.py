"""
Router Node — Query Complexity Classification (PageIndex)

Classifies incoming queries to route them to the appropriate processing path.
Uses heuristics first, then LLM for borderline cases.

Async + InjectedState pattern.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import time
from typing import Any, Literal

from ..schemas.state import PageIndexQueryState
from ..schemas.injected import get_deps
from ...observability.logging import get_logger

logger = get_logger(__name__)

ROUTER_PROMPT = """Analyze the following query and classify its complexity.

Query: {question}

Classification criteria:
- SIMPLE: Direct factual questions, single concept lookup (e.g., "What is X?")
- STANDARD: Questions requiring context synthesis from multiple sections
- COMPLEX: Multi-part questions or questions requiring analysis
- MULTI_HOP: Questions requiring reasoning across multiple documents or steps

Respond with ONLY one word: SIMPLE, STANDARD, COMPLEX, or MULTI_HOP"""

async def classify_query(
    state: PageIndexQueryState, config: RunnableConfig
) -> dict[str, Any]:
    """
    🔀 ROUTER — Classify query complexity for routing.

    Uses fast heuristics first. For borderline cases (score 0.3-0.7),
    calls LLM for classification.

    Args:
        state: Current state with question field.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with query_type and complexity_score.
    """
    start_time = time.time()
    deps = get_deps(config)
    question = state["question"]

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="router",
        input_summary={"question_length": len(question)},
    )

    try:
        # Quick heuristics first
        complexity_score = _compute_complexity_heuristics(question)

        # For borderline cases, use LLM classification
        if 0.3 < complexity_score < 0.7:
            llm_start = time.time()
            response = await deps.llm.agenerate(
                ROUTER_PROMPT.format(question=question),
                model="llama-3.1-8b-instant",
                max_tokens=10,
                temperature=0.0,
            )
            llm_latency = (time.time() - llm_start) * 1000

            await deps.telemetry.log_llm_call(
                query_id=state.get("query_id", ""),
                node_name="router",
                model="llama-3.1-8b-instant",
                latency_ms=round(llm_latency, 1),
                temperature=0.0,
            )

            query_type = _parse_classification(response)
        else:
            query_type = _score_to_type(complexity_score)

        duration_ms = (time.time() - start_time) * 1000

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="router",
            output_summary={"query_type": query_type, "complexity_score": complexity_score},
            duration_ms=duration_ms,
        )

        logger.info(
            "router.classified",
            query_type=query_type,
            complexity_score=round(complexity_score, 3),
        )

        return {
            "query_type": query_type,
            "complexity_score": complexity_score,
        }

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("router.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="router",
            duration_ms=duration_ms,
            error=str(exc),
        )
        # Fallback: route as standard
        return {"query_type": "standard", "complexity_score": 0.5}

def _compute_complexity_heuristics(question: str) -> float:
    """Compute complexity score using text heuristics."""
    score = 0.3

    if len(question) > 200:
        score += 0.2
    elif len(question) > 100:
        score += 0.1

    multi_part_words = ["and", "also", "additionally", "compare", "contrast", "versus"]
    for word in multi_part_words:
        if word in question.lower():
            score += 0.15

    analysis_words = ["analyze", "explain why", "how does", "what caused", "impact of"]
    for phrase in analysis_words:
        if phrase in question.lower():
            score += 0.2

    calc_words = ["calculate", "compute", "total", "sum", "average", "percentage"]
    for word in calc_words:
        if word in question.lower():
            score += 0.15

    return min(score, 1.0)

def _parse_classification(
    response: str,
) -> Literal["simple", "standard", "complex", "multi_hop"]:
    """Parse LLM classification response."""
    response = response.strip().upper()
    if "SIMPLE" in response:
        return "simple"
    elif "MULTI_HOP" in response or "MULTI-HOP" in response:
        return "multi_hop"
    elif "COMPLEX" in response:
        return "complex"
    return "standard"

def _score_to_type(
    score: float,
) -> Literal["simple", "standard", "complex", "multi_hop"]:
    """Convert complexity score to query type."""
    if score < 0.3:
        return "simple"
    elif score < 0.6:
        return "standard"
    elif score < 0.8:
        return "complex"
    return "multi_hop"
