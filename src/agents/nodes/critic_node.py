"""
Critic Node - Evaluate Retrieval Quality

Assesses whether retrieved documents are sufficient to answer the query.
"""

from ..schemas.state import AgentState, CriticEvaluation
from ...llm.groq_client import GroqClient
from ...observability.tracing import tracer
from ...observability.metrics import RELEVANCE_SCORE


CRITIC_PROMPT = """You are evaluating whether retrieved documents can answer a query.

Query: {question}

Retrieved Documents:
{context}

Evaluate on a scale of 0-1:
1. RELEVANCE: Are the documents relevant to the query?
2. COMPLETENESS: Do they contain enough information to fully answer?
3. CONFIDENCE: How confident are you that a good answer can be generated?

If scores are low (< 0.5), suggest a refined search query.

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


def evaluate_retrieval(state: AgentState) -> dict:
    """
    Node: Evaluate if retrieved docs can answer the query.
    
    Input: question, reranked_docs
    Output: relevance_score, groundedness_score, needs_retry, retry_count
    """
    with tracer.start_as_current_span("critic_node") as span:
        question = state["question"]
        docs = state.get("reranked_docs", [])
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        
        # Build context from documents
        context = "\n\n".join([
            f"[Doc {i+1}] (score: {doc.get('score', 0):.2f})\n{doc.get('content', '')[:500]}"
            for i, doc in enumerate(docs[:5])
        ])
        
        # If no documents, definitely need retry
        if not docs:
            span.set_attribute("needs_retry", True)
            return {
                "relevance_score": 0.0,
                "groundedness_score": 0.0,
                "needs_retry": retry_count < max_retries,
                "retry_count": retry_count + 1
            }
        
        # Use LLM to evaluate
        llm = GroqClient()
        response = llm.generate(
            CRITIC_PROMPT.format(question=question, context=context),
            model="llama-3.1-8b-instant",  # Fast model for evaluation
            max_tokens=200
        )
        
        evaluation = _parse_evaluation(response)
        
        # Record metrics
        RELEVANCE_SCORE.observe(evaluation.relevance_score)
        span.set_attribute("relevance_score", evaluation.relevance_score)
        span.set_attribute("needs_retry", evaluation.needs_retry)
        
        # Determine if retry is needed
        should_retry = (
            evaluation.needs_retry and 
            retry_count < max_retries and
            evaluation.relevance_score < 0.5
        )
        
        return {
            "relevance_score": evaluation.relevance_score,
            "groundedness_score": evaluation.groundedness_score,
            "needs_retry": should_retry,
            "retry_count": retry_count + 1 if should_retry else retry_count
        }


def _parse_evaluation(response: str) -> CriticEvaluation:
    """Parse critic evaluation from LLM response"""
    import json
    
    try:
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        
        data = json.loads(response)
        
        return CriticEvaluation(
            relevance_score=float(data.get("relevance_score", 0.5)),
            groundedness_score=float(data.get("completeness_score", 0.5)),
            completeness_score=float(data.get("confidence_score", 0.5)),
            needs_retry=data.get("needs_retry", False),
            feedback=data.get("feedback", ""),
            suggested_query=data.get("suggested_query")
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        # Fallback: assume decent quality
        return CriticEvaluation(
            relevance_score=0.6,
            groundedness_score=0.6,
            completeness_score=0.6,
            needs_retry=False,
            feedback="Could not parse evaluation"
        )
