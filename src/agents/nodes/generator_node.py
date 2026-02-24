"""
Generator Node — Answer Generation with Page-Level Citations (PageIndex)

Generates the final answer using extracted page content.
Includes specific page citations: "Source: Balance Sheet, p.24"

Updated for PageIndex pipeline: uses page_contents and context instead
of vector-retrieved chunks.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import time
from typing import Any

from ..schemas.state import PageIndexQueryState
from ..schemas.injected import get_deps
from ...observability.logging import get_logger

logger = get_logger(__name__)

_GENERATOR_PROMPT = """You are a helpful finance assistant. Answer the question using ONLY the provided document pages.

Document Pages:
{context}

Question: {question}

Instructions:
1. Answer based ONLY on the provided page content
2. If the content doesn't contain enough information, say so
3. Be concise but comprehensive
4. Include specific numbers, dates, or facts when available
5. Do NOT make up information not in the pages
6. Cite your sources using page numbers, e.g., (Source: filename, p.XX)

Answer:"""

_FAST_GENERATOR_PROMPT = """Answer this finance question using the document content below.

Content:
{context}

Question: {question}

Answer concisely with page citations:"""

async def generate_response(
    state: PageIndexQueryState, config: RunnableConfig
) -> dict[str, Any]:
    """
    🤖 GENERATOR — Generate answer with page-level citations.

    Generates the final answer using extracted page content.
    Uses the full quality model for comprehensive answers.

    Args:
        state: Current state with question, context, page_contents.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with answer, sources, and confidence.
    """
    start_time = time.time()
    deps = get_deps(config)
    question = state["question"]
    context = state.get("context", "")
    page_contents = state.get("page_contents", [])
    relevance_score = state.get("relevance_score", 0.5)

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="generator",
        input_summary={
            "context_length": len(context),
            "page_count": len(page_contents),
        },
    )

    try:
        # Build sources list
        sources = _build_sources(page_contents)

        # Generate response
        llm_start = time.time()
        answer = await deps.llm.agenerate(
            _GENERATOR_PROMPT.format(question=question, context=context),
            model="llama-3.3-70b-versatile",
            max_tokens=1024,
            temperature=0.1,
        )
        llm_latency = (time.time() - llm_start) * 1000

        await deps.telemetry.log_llm_call(
            query_id=state.get("query_id", ""),
            node_name="generator",
            model="llama-3.3-70b-versatile",
            latency_ms=round(llm_latency, 1),
            temperature=0.1,
        )

        # Calculate confidence
        confidence = _calculate_confidence(relevance_score, page_contents, answer)

        duration_ms = (time.time() - start_time) * 1000

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="generator",
            output_summary={
                "answer_length": len(answer),
                "source_count": len(sources),
                "confidence": round(confidence, 3),
            },
            duration_ms=duration_ms,
        )

        return {
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
        }

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("generator.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="generator",
            duration_ms=duration_ms,
            error=str(exc),
        )
        await deps.telemetry.log_error(
            error_type=type(exc).__name__,
            error_message=str(exc),
            query_id=state.get("query_id", ""),
            node_name="generator",
            exception=exc,
            recovery_action="return_error",
        )
        return {
            "answer": "An error occurred while generating the answer.",
            "sources": [],
            "confidence": 0.0,
            "error": str(exc),
        }

async def generate_response_fast(
    state: PageIndexQueryState, config: RunnableConfig
) -> dict[str, Any]:
    """
    ⚡ FAST GENERATOR — Quick response for simple queries.

    Uses faster model with shorter prompt for the simple query path.

    Args:
        state: Current state with question and context.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with answer, sources, and confidence.
    """
    start_time = time.time()
    deps = get_deps(config)
    question = state["question"]
    context = state.get("context", "")
    page_contents = state.get("page_contents", [])

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="fast_generator",
        input_summary={"context_length": len(context)},
    )

    try:
        # Shorter context for fast path
        short_context = context[:2000]
        sources = _build_sources(page_contents[:3])

        llm_start = time.time()
        answer = await deps.llm.agenerate(
            _FAST_GENERATOR_PROMPT.format(question=question, context=short_context),
            model="llama-3.1-8b-instant",
            max_tokens=1024,
            temperature=0.1,
        )
        llm_latency = (time.time() - llm_start) * 1000

        await deps.telemetry.log_llm_call(
            query_id=state.get("query_id", ""),
            node_name="fast_generator",
            model="llama-3.1-8b-instant",
            latency_ms=round(llm_latency, 1),
            temperature=0.1,
        )

        duration_ms = (time.time() - start_time) * 1000

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="fast_generator",
            output_summary={"answer_length": len(answer)},
            duration_ms=duration_ms,
        )

        return {
            "answer": answer,
            "sources": sources,
            "confidence": 0.7,
        }

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("fast_generator.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="fast_generator",
            duration_ms=duration_ms,
            error=str(exc),
        )
        return {
            "answer": "An error occurred while generating the answer.",
            "sources": [],
            "confidence": 0.0,
            "error": str(exc),
        }

def _build_sources(page_contents: list[dict]) -> list[dict]:
    """Build source citations from page contents."""
    sources: list[dict] = []
    seen: set[str] = set()

    for pc in page_contents:
        key = f"{pc.get('doc_id', '')}:p{pc.get('page_num', 0)}"
        if key not in seen:
            sources.append({
                "doc_id": pc.get("doc_id", ""),
                "page_num": pc.get("page_num", 0),
                "filename": pc.get("filename", ""),
            })
            seen.add(key)

    return sources

def _calculate_confidence(
    relevance: float, page_contents: list[dict], answer: str
) -> float:
    """Calculate overall confidence score."""
    confidence = relevance * 0.5

    if len(page_contents) >= 3:
        confidence += 0.15
    elif len(page_contents) >= 1:
        confidence += 0.05

    if len(answer) > 100:
        confidence += 0.1

    uncertainty_phrases = ["i'm not sure", "unclear", "cannot determine", "no information"]
    for phrase in uncertainty_phrases:
        if phrase in answer.lower():
            confidence -= 0.2

    return max(0.0, min(1.0, confidence + 0.25))
