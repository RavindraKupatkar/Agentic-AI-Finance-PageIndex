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

ROUTER_PROMPT = """Classify this financial document query:

Query: {question}

Rules:
- SIMPLE: Single fact lookup ("What is the revenue?", "When was X filed?")
- STANDARD: Requires reading 1-2 sections ("Summarize the balance sheet")
- COMPLEX: Multi-part analysis or comparison across sections
- MULTI_HOP: Requires cross-document reasoning or multi-step calculation

Respond with ONLY: SIMPLE, STANDARD, COMPLEX, or MULTI_HOP"""

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
    """Compute complexity score using text heuristics with finance awareness."""
    score = 0.2  # Lower base score reduces borderline LLM calls
    q = question.lower()

    if len(question) > 200:
        score += 0.2
    elif len(question) > 100:
        score += 0.1

    # Multi-document / comparison → immediate complex
    multi_part_words = ["compare", "contrast", "versus", "difference between", "all attached files", "across documents"]
    for word in multi_part_words:
        if word in q:
            score += 0.8

    # Conjunctions suggesting multi-part queries
    multi_part_and = ["and also", "additionally", "furthermore", "as well as"]
    for word in multi_part_and:
        if word in q:
            score += 0.15

    # Analysis keywords
    analysis_words = ["analyze", "explain why", "how does", "what caused", "impact of", "trend", "year-over-year"]
    for phrase in analysis_words:
        if phrase in q:
            score += 0.2

    # Calculation keywords
    calc_words = ["calculate", "compute", "total", "sum", "average", "percentage", "ratio", "margin"]
    for word in calc_words:
        if word in q:
            score += 0.15

    # Simple finance lookups → bias toward SIMPLE (reduce score)
    simple_finance = ["what is the", "what was the", "how much", "when was", "where is", "total revenue",
                      "total debt", "net income", "ebitda", "eps", "operating income", "balance sheet"]
    simple_matches = sum(1 for phrase in simple_finance if phrase in q)
    if simple_matches >= 1 and score < 0.5:
        score -= 0.1  # Push simple lookups below the LLM threshold

    return max(0.0, min(score, 1.0))

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
