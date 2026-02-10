"""
Router Node - Query Complexity Classification

Classifies incoming queries to route them to the appropriate processing path.
"""

from typing import Literal
from ..schemas.state import AgentState
from ...llm.groq_client import GroqClient
from ...observability.tracing import tracer


ROUTER_PROMPT = """Analyze the following query and classify its complexity.

Query: {question}

Classification criteria:
- SIMPLE: Direct factual questions, single concept lookup (e.g., "What is X?")
- STANDARD: Questions requiring context synthesis from multiple chunks
- COMPLEX: Multi-part questions or questions requiring analysis
- MULTI_HOP: Questions requiring reasoning across multiple documents or steps

Respond with ONLY one word: SIMPLE, STANDARD, COMPLEX, or MULTI_HOP"""


def classify_query(state: AgentState) -> dict:
    """
    Node: Classify query complexity for routing.
    
    Input: question
    Output: query_type, complexity_score
    """
    with tracer.start_as_current_span("router_node") as span:
        question = state["question"]
        span.set_attribute("question_length", len(question))
        
        # Quick heuristics first
        complexity_score = _compute_complexity_heuristics(question)
        
        # For borderline cases, use LLM classification
        if 0.3 < complexity_score < 0.7:
            llm = GroqClient()
            response = llm.generate(
                ROUTER_PROMPT.format(question=question),
                model="llama-3.1-8b-instant",  # Fast model for routing
                max_tokens=10
            )
            query_type = _parse_classification(response)
        else:
            query_type = _score_to_type(complexity_score)
        
        span.set_attribute("query_type", query_type)
        span.set_attribute("complexity_score", complexity_score)
        
        return {
            "query_type": query_type,
            "complexity_score": complexity_score
        }


def _compute_complexity_heuristics(question: str) -> float:
    """Compute complexity score using heuristics"""
    score = 0.3  # Base score
    
    # Length-based
    if len(question) > 200:
        score += 0.2
    elif len(question) > 100:
        score += 0.1
    
    # Multi-part indicators
    multi_part_words = ["and", "also", "additionally", "compare", "contrast", "versus"]
    for word in multi_part_words:
        if word in question.lower():
            score += 0.15
    
    # Analysis indicators  
    analysis_words = ["analyze", "explain why", "how does", "what caused", "impact of"]
    for phrase in analysis_words:
        if phrase in question.lower():
            score += 0.2
    
    # Calculation indicators
    calc_words = ["calculate", "compute", "total", "sum", "average", "percentage"]
    for word in calc_words:
        if word in question.lower():
            score += 0.15
    
    return min(score, 1.0)


def _parse_classification(response: str) -> Literal["simple", "standard", "complex", "multi_hop"]:
    """Parse LLM classification response"""
    response = response.strip().upper()
    
    if "SIMPLE" in response:
        return "simple"
    elif "MULTI_HOP" in response or "MULTI-HOP" in response:
        return "multi_hop"
    elif "COMPLEX" in response:
        return "complex"
    return "standard"


def _score_to_type(score: float) -> Literal["simple", "standard", "complex", "multi_hop"]:
    """Convert complexity score to query type"""
    if score < 0.3:
        return "simple"
    elif score < 0.6:
        return "standard"
    elif score < 0.8:
        return "complex"
    return "multi_hop"
