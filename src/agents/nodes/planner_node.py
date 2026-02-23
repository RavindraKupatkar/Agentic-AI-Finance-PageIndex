"""
Planner Node — Break Complex Queries into Sub-Steps (PageIndex)

For complex/multi-hop queries, creates an execution plan
before tree search. Updated for PageIndex pipeline.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import json
import time
from typing import Any

from ..schemas.state import PageIndexQueryState
from ..schemas.injected import get_deps
from ...observability.logging import get_logger

logger = get_logger(__name__)

_PLANNER_PROMPT = """You are a financial analysis expert. Break this complex question into simpler sub-questions that can each be answered by searching a document tree index.

Original Question: {question}

Create a plan with 2-4 steps. Each step should be a focused sub-question.

Output as JSON:
{{
    "steps": [
        {{
            "step_id": 1,
            "action": "retrieve",
            "query": "Sub-question to search for",
            "rationale": "Why this step is needed"
        }}
    ]
}}

Only output JSON."""

async def create_plan(
    state: PageIndexQueryState, config: RunnableConfig
) -> dict[str, Any]:
    """
    📝 PLANNER — Break complex queries into sub-steps.

    For complex/multi-hop queries, creates an execution plan
    that the tree search can follow step by step.

    Args:
        state: Current state with question field.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with plan (list of steps) and current_step.
    """
    start_time = time.time()
    deps = get_deps(config)
    question = state["question"]

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="planner",
        input_summary={"question_length": len(question)},
    )

    try:
        llm_start = time.time()
        response = await deps.llm.agenerate(
            _PLANNER_PROMPT.format(question=question),
            model="llama-3.3-70b-versatile",
            max_tokens=512,
            temperature=0.1,
        )
        llm_latency = (time.time() - llm_start) * 1000

        await deps.telemetry.log_llm_call(
            query_id=state.get("query_id", ""),
            node_name="planner",
            model="llama-3.3-70b-versatile",
            latency_ms=round(llm_latency, 1),
            temperature=0.1,
        )

        plan = _parse_plan(response)

        duration_ms = (time.time() - start_time) * 1000

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="planner",
            output_summary={"steps": len(plan)},
            duration_ms=duration_ms,
        )

        logger.info("planner.created", steps=len(plan))

        return {
            "plan": plan,
            "current_step": 0,
        }

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("planner.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="planner",
            duration_ms=duration_ms,
            error=str(exc),
        )
        # Fallback: single-step plan with original question
        return {
            "plan": [{"step_id": 1, "action": "retrieve", "query": question, "rationale": "Fallback"}],
            "current_step": 0,
        }

def _parse_plan(response: str) -> list[dict]:
    """Parse plan from LLM response."""
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
        steps = data.get("steps", [])

        if isinstance(steps, list) and len(steps) > 0:
            return steps
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    return []
