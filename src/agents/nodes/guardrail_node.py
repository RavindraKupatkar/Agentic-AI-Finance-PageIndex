"""
Guardrail Node - Input/Output Safety Validation

Implements safety checks using LLM Guard and custom finance rules.
"""

from typing import List

from ..schemas.state import AgentState
from ...guardrails.input_guards import InputGuard
from ...guardrails.output_guards import OutputGuard
from ...guardrails.finance_compliance import FinanceComplianceGuard
from ...observability.tracing import tracer
from ...observability.metrics import GUARDRAIL_BLOCKS


def validate_input(state: AgentState) -> dict:
    """
    Node: Validate user input before processing.
    
    Checks:
    - Prompt injection
    - Toxic content
    - PII detection and masking
    
    Input: question
    Output: input_valid, guardrail_warnings, question (sanitized)
    """
    with tracer.start_as_current_span("input_guard_node") as span:
        question = state["question"]
        warnings: List[str] = []
        
        guard = InputGuard()
        
        # Run input validation
        is_valid, sanitized_question, issues = guard.validate(question)
        
        if issues:
            warnings.extend(issues)
            span.set_attribute("issues_found", len(issues))
        
        if not is_valid:
            GUARDRAIL_BLOCKS.labels(type="input").inc()
        
        span.set_attribute("input_valid", is_valid)
        
        return {
            "input_valid": is_valid,
            "guardrail_warnings": warnings,
            "question": sanitized_question
        }


def validate_output(state: AgentState) -> dict:
    """
    Node: Validate LLM output before returning to user.
    
    Checks:
    - Hallucination detection
    - PII in response
    - Finance compliance (no investment advice)
    - Adds required disclaimers
    
    Input: answer, reranked_docs, sources
    Output: output_valid, answer (with disclaimers), guardrail_warnings
    """
    with tracer.start_as_current_span("output_guard_node") as span:
        answer = state.get("answer", "")
        docs = state.get("reranked_docs", [])
        warnings = state.get("guardrail_warnings", [])
        
        output_guard = OutputGuard()
        finance_guard = FinanceComplianceGuard()
        
        # Validate output
        is_valid, cleaned_answer, issues = output_guard.validate(answer, docs)
        warnings.extend(issues)
        
        # Apply finance compliance
        cleaned_answer = finance_guard.process_response(cleaned_answer)
        
        if not is_valid:
            GUARDRAIL_BLOCKS.labels(type="output").inc()
        
        span.set_attribute("output_valid", is_valid)
        span.set_attribute("warnings_count", len(warnings))
        
        return {
            "output_valid": is_valid,
            "answer": cleaned_answer,
            "guardrail_warnings": warnings
        }


def create_error_response(state: AgentState) -> dict:
    """
    Node: Create error response when input validation fails.
    """
    warnings = state.get("guardrail_warnings", [])
    
    error_message = (
        "I'm unable to process this request. "
        "Please ensure your question is appropriate and try again."
    )
    
    if "prompt_injection" in str(warnings).lower():
        error_message = "I detected a potential security issue with your request."
    elif "toxic" in str(warnings).lower():
        error_message = "I'm unable to respond to requests with inappropriate content."
    
    return {
        "answer": error_message,
        "sources": [],
        "confidence": 0.0,
        "error": "Input validation failed"
    }
