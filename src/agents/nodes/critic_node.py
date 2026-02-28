"""
Critic Node — Evaluate Page Content Quality (PageIndex)

Evaluates whether the retrieved page content is sufficient to answer
the user's question. If not, provides a refined_query for retry.

Updated for PageIndex pipeline: evaluates page content instead of chunks.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import json
import time
from typing import Any

from ..schemas.state import PageIndexQueryState, CriticEvaluation
from ..schemas.injected import get_deps
from ...observability.logging import get_logger

logger = get_logger(__name__)

_CRITIC_PROMPT = """Evaluate whether the retrieved document pages can answer this question.

Question: {question}

Retrieved Page Content:
{context}

Evaluate on a scale of 0-1:
1. RELEVANCE: Are the pages relevant to the question?
2. COMPLETENESS: Do they contain enough information to fully answer?
3. CONFIDENCE: How confident are you that a good answer can be generated?

If scores are low (< 0.5), suggest a refined search query that might find better content.

Output as JSON:
{{
    "relevance_score": 0.0-1.0,
    "completeness_score": 0.0-1.0,
    "confidence_score": 0.0-1.0,
    "needs_retry": true/false,
    "feedback": "explanation",
    "suggested_query": "refined query if retry needed"
}}

Only output JSON."""

async def evaluate_retrieval(
    state: PageIndexQueryState, config: RunnableConfig
) -> dict[str, Any]:
    """
    🔍 CRITIC — Evaluate whether retrieved pages answer the question.

    Evaluates:
    - Relevance: Do the pages relate to the question?
    - Completeness: Is there enough info to answer?

    If insufficient, sets needs_retry=True and provides refined_query.

    Args:
        state: Current state with question, page_contents, context.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with relevance_score, groundedness_score, needs_retry, refined_query.
    """
    start_time = time.time()
    deps = get_deps(config)
    question = state["question"]
    context = state.get("context", "")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="critic",
        input_summary={
            "context_length": len(context),
            "retry_count": retry_count,
        },
    )

    try:
        # If no context at all, definitely retry
        if not context.strip():
            duration_ms = (time.time() - start_time) * 1000
            should_retry = retry_count < max_retries
            await deps.telemetry.log_node_end(
                node_execution_id=node_exec_id,
                query_id=state.get("query_id", ""),
                node_name="critic",
                output_summary={"needs_retry": should_retry, "reason": "empty_context"},
                duration_ms=duration_ms,
            )
            return {
                "relevance_score": 0.0,
                "groundedness_score": 0.0,
                "needs_retry": should_retry,
                "retry_count": retry_count + 1 if should_retry else retry_count,
                "refined_query": question,  # Retry with same query
            }

        # Use LLM to evaluate
        # Truncate context for evaluation prompt
        eval_context = context[:3000]

        llm_start = time.time()
        response = await deps.llm.agenerate(
            _CRITIC_PROMPT.format(question=question, context=eval_context),
            model="llama-3.3-70b-versatile",
            max_tokens=300,
            temperature=0.1,
        )
        llm_latency = (time.time() - llm_start) * 1000

        await deps.telemetry.log_llm_call(
            query_id=state.get("query_id", ""),
            node_name="critic",
            model="llama-3.3-70b-versatile",
            latency_ms=round(llm_latency, 1),
            temperature=0.1,
        )

        evaluation = _parse_evaluation(response)

        # Determine retry
        should_retry = (
            evaluation.needs_retry
            and retry_count < max_retries
            and evaluation.relevance_score < 0.5
        )

        duration_ms = (time.time() - start_time) * 1000

        result: dict[str, Any] = {
            "relevance_score": evaluation.relevance_score,
            "groundedness_score": evaluation.groundedness_score,
            "needs_retry": should_retry,
            "retry_count": retry_count + 1 if should_retry else retry_count,
        }

        if should_retry and evaluation.suggested_query:
            result["refined_query"] = evaluation.suggested_query

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="critic",
            output_summary={
                "relevance": evaluation.relevance_score,
                "needs_retry": should_retry,
            },
            duration_ms=duration_ms,
        )

        logger.info(
            "critic.evaluated",
            relevance=evaluation.relevance_score,
            needs_retry=should_retry,
        )

        return result

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("critic.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="critic",
            duration_ms=duration_ms,
            error=str(exc),
        )
        # Fail open — proceed to generation
        return {
            "relevance_score": 0.6,
            "groundedness_score": 0.6,
            "needs_retry": False,
            "retry_count": retry_count,
        }

def _parse_evaluation(response: str) -> CriticEvaluation:
    """Parse critic evaluation from LLM response."""
    try:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}") + 1
        if start_idx >= 0 and end_idx > start_idx:
            cleaned = cleaned[start_idx:end_idx]

        data = json.loads(cleaned)

        return CriticEvaluation(
            relevance_score=float(data.get("relevance_score", 0.5)),
            groundedness_score=float(data.get("completeness_score", 0.5)),
            completeness_score=float(data.get("confidence_score", 0.5)),
            needs_retry=data.get("needs_retry", False),
            feedback=data.get("feedback", ""),
            suggested_query=data.get("suggested_query"),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return CriticEvaluation(
            relevance_score=0.6,
            groundedness_score=0.6,
            completeness_score=0.6,
            needs_retry=False,
            feedback="Could not parse evaluation",
        )
