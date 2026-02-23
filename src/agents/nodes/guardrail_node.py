"""
Guardrail Node — Input Validation, Output Checks, and Error Responses

Three LangGraph node functions:
    - validate_input:  PII detection, prompt injection, query length validation
    - validate_output: Hallucination heuristics, finance compliance checks
    - create_error_response: Graceful error message for rejected inputs

All nodes use async + InjectedState pattern.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import re
import time
from typing import Any

from ..schemas.state import PageIndexQueryState
from ..schemas.injected import get_deps
from ...observability.logging import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# PII patterns and injection signatures
# ──────────────────────────────────────────────────────────────

_PII_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
    (r"\b\d{16}\b", "credit_card"),
    (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "credit_card"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email"),
    (r"\b\d{3}[\s.-]?\d{3}[\s.-]?\d{4}\b", "phone"),
]

_INJECTION_SIGNATURES = [
    "ignore previous instructions",
    "ignore all instructions",
    "forget your instructions",
    "you are now",
    "act as if",
    "pretend you are",
    "system prompt",
    "reveal your prompt",
    "output your instructions",
    "disregard",
    "override",
    "jailbreak",
]

_FINANCIAL_DISCLAIMER_TRIGGERS = [
    "investment advice",
    "buy this stock",
    "guaranteed returns",
    "financial recommendation",
    "should i invest",
]

# ──────────────────────────────────────────────────────────────
# Node: Input Guard
# ──────────────────────────────────────────────────────────────

async def validate_input(
    state: PageIndexQueryState, config: RunnableConfig
) -> dict[str, Any]:
    """
    🛡️ INPUT GUARD — PII masking + prompt injection detection.

    Validates the user's question before it enters the RAG pipeline:
    1. Query length check (min/max from config)
    2. PII detection and masking (SSN, credit cards, emails, phones)
    3. Prompt injection detection (known attack patterns)

    Args:
        state: Current PageIndexQueryState with question field.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with input_valid, guardrail_warnings, and potentially
        masked question.
    """
    start_time = time.time()
    deps = get_deps(config)
    question = state["question"]
    warnings: list[str] = []

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="input_guard",
        input_summary={"question_length": len(question)},
    )

    try:
        # 1. Length check
        if len(question.strip()) < 3:
            duration_ms = (time.time() - start_time) * 1000
            await deps.telemetry.log_node_end(
                node_execution_id=node_exec_id,
                query_id=state.get("query_id", ""),
                node_name="input_guard",
                output_summary={"rejected": True, "reason": "too_short"},
                duration_ms=duration_ms,
            )
            return {
                "input_valid": False,
                "guardrail_warnings": ["Query too short (minimum 3 characters)"],
                "error": "Query too short. Please provide a more detailed question.",
            }

        if len(question) > 2000:
            duration_ms = (time.time() - start_time) * 1000
            await deps.telemetry.log_node_end(
                node_execution_id=node_exec_id,
                query_id=state.get("query_id", ""),
                node_name="input_guard",
                output_summary={"rejected": True, "reason": "too_long"},
                duration_ms=duration_ms,
            )
            return {
                "input_valid": False,
                "guardrail_warnings": [f"Query too long ({len(question)} chars, max 2000)"],
                "error": "Query exceeds maximum length of 2000 characters.",
            }

        # 2. PII detection
        masked_question = question
        for pattern, pii_type in _PII_PATTERNS:
            matches = re.findall(pattern, question)
            if matches:
                warnings.append(f"PII detected: {pii_type} ({len(matches)} occurrence(s))")
                masked_question = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", masked_question)

        # 3. Prompt injection detection
        question_lower = question.lower()
        for signature in _INJECTION_SIGNATURES:
            if signature in question_lower:
                duration_ms = (time.time() - start_time) * 1000
                await deps.telemetry.log_node_end(
                    node_execution_id=node_exec_id,
                    query_id=state.get("query_id", ""),
                    node_name="input_guard",
                    output_summary={"rejected": True, "reason": "injection_detected"},
                    duration_ms=duration_ms,
                )
                await deps.telemetry.log_error(
                    error_type="PromptInjection",
                    error_message=f"Injection signature detected: '{signature}'",
                    query_id=state.get("query_id", ""),
                    node_name="input_guard",
                    recovery_action="reject",
                )
                return {
                    "input_valid": False,
                    "guardrail_warnings": ["Potential prompt injection detected"],
                    "error": "Your query was flagged for potential prompt injection. Please rephrase.",
                }

        # 4. Financial disclaimer check (warning only, not rejection)
        for trigger in _FINANCIAL_DISCLAIMER_TRIGGERS:
            if trigger in question_lower:
                warnings.append(
                    "Financial advice disclaimer: This system provides information, not financial advice."
                )
                break

        duration_ms = (time.time() - start_time) * 1000
        result = {
            "input_valid": True,
            "guardrail_warnings": warnings,
        }

        # If question was masked, use masked version
        if masked_question != question:
            result["question"] = masked_question

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="input_guard",
            output_summary={"valid": True, "warnings": len(warnings)},
            duration_ms=duration_ms,
        )

        return result

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("input_guard.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="input_guard",
            duration_ms=duration_ms,
            error=str(exc),
        )
        # Fail open — let the query through on guardrail failure
        return {
            "input_valid": True,
            "guardrail_warnings": [f"Input guard error: {str(exc)}"],
        }

# ──────────────────────────────────────────────────────────────
# Node: Output Guard
# ──────────────────────────────────────────────────────────────

async def validate_output(
    state: PageIndexQueryState, config: RunnableConfig
) -> dict[str, Any]:
    """
    🛡️ OUTPUT GUARD — Hallucination heuristics + finance compliance.

    Validates the generated answer before returning it to the user:
    1. Check if answer references content not in the provided context
    2. Check for overly confident financial claims
    3. Add disclaimers if needed

    Args:
        state: Current state with answer, context, and sources.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with output_valid, guardrail_warnings, and potentially
        modified answer.
    """
    start_time = time.time()
    deps = get_deps(config)
    answer = state.get("answer", "") or ""
    warnings: list[str] = state.get("guardrail_warnings", []).copy()

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="output_guard",
        input_summary={"answer_length": len(answer)},
    )

    try:
        modified_answer = answer

        # 1. Check for empty/too-short answer
        if len(answer.strip()) < 10:
            warnings.append("Answer too short — may be incomplete")

        # 2. Check for hallucination indicators
        hallucination_phrases = [
            "based on my knowledge",
            "as an ai",
            "i believe",
            "i think",
            "from my training",
            "according to my",
        ]
        answer_lower = answer.lower()
        for phrase in hallucination_phrases:
            if phrase in answer_lower:
                warnings.append(f"Possible hallucination indicator: '{phrase}'")

        # 3. Financial compliance — add disclaimer if needed
        financial_claims = [
            "guaranteed",
            "will increase",
            "will decrease",
            "definitely",
            "certainly",
            "risk-free",
        ]
        for claim in financial_claims:
            if claim in answer_lower:
                warnings.append(f"Financial compliance flag: '{claim}'")
                if "\n\n*Disclaimer:" not in modified_answer:
                    modified_answer += (
                        "\n\n*Disclaimer: This information is extracted from the document and "
                        "should not be considered financial advice. Please consult a qualified "
                        "financial advisor for investment decisions.*"
                    )
                break

        # 4. Check if sources are present
        sources = state.get("sources", [])
        if not sources and len(answer.strip()) > 50:
            warnings.append("Answer generated without source citations")

        duration_ms = (time.time() - start_time) * 1000

        result: dict[str, Any] = {
            "output_valid": True,
            "guardrail_warnings": warnings,
        }

        if modified_answer != answer:
            result["answer"] = modified_answer

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="output_guard",
            output_summary={"valid": True, "warnings": len(warnings)},
            duration_ms=duration_ms,
        )

        return result

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("output_guard.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="output_guard",
            duration_ms=duration_ms,
            error=str(exc),
        )
        return {"output_valid": True, "guardrail_warnings": warnings}

# ──────────────────────────────────────────────────────────────
# Node: Error Response
# ──────────────────────────────────────────────────────────────

async def create_error_response(
    state: PageIndexQueryState, config: RunnableConfig
) -> dict[str, Any]:
    """
    ❌ ERROR RESPONSE — Generate error message for rejected inputs.

    Called when input_guard rejects a query. Produces a user-friendly
    error message.

    Args:
        state: Current state with error and guardrail_warnings.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with answer, sources, and confidence set for error state.
    """
    deps = get_deps(config)
    error_msg = state.get("error", "Your query could not be processed.")
    warnings = state.get("guardrail_warnings", [])

    logger.info(
        "error_response.created",
        error=error_msg,
        warnings=warnings,
    )

    await deps.telemetry.log_error(
        error_type="InputRejected",
        error_message=error_msg,
        query_id=state.get("query_id", ""),
        node_name="error_response",
        recovery_action="return_error",
    )

    return {
        "answer": error_msg,
        "sources": [],
        "confidence": 0.0,
        "output_valid": True,  # Skip output guard for error responses
    }
