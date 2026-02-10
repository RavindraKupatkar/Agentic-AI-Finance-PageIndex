"""
Generator Node - LLM Response Generation

Generates final response using context from retrieved documents.
"""

from typing import List, AsyncGenerator

from ..schemas.state import AgentState
from ...llm.groq_client import GroqClient
from ...observability.tracing import tracer
from ...observability.metrics import GENERATION_LATENCY, LLM_TOKENS


GENERATOR_PROMPT = """You are a helpful finance assistant. Answer the question using ONLY the provided context.

Context:
{context}

Question: {question}

Instructions:
1. Answer based ONLY on the provided context
2. If the context doesn't contain enough information, say so
3. Be concise but comprehensive
4. Include specific numbers, dates, or facts when available
5. Do NOT make up information not in the context

Answer:"""


FAST_GENERATOR_PROMPT = """Answer this finance question using the context below.

Context:
{context}

Question: {question}

Answer concisely:"""


def generate_response(state: AgentState) -> dict:
    """
    Node: Generate response using retrieved context.
    
    Input: question, reranked_docs
    Output: answer, sources, confidence
    """
    with tracer.start_as_current_span("generator_node") as span:
        question = state["question"]
        docs = state.get("reranked_docs", [])
        relevance_score = state.get("relevance_score", 0.5)
        
        # Build context
        context = _build_context(docs)
        sources = _extract_sources(docs)
        
        span.set_attribute("context_length", len(context))
        span.set_attribute("source_count", len(sources))
        
        # Generate response
        llm = GroqClient()
        answer = llm.generate(
            GENERATOR_PROMPT.format(question=question, context=context),
            model="llama-3.3-70b-versatile",  # Quality model for generation
            max_tokens=1024
        )
        
        # Calculate confidence based on relevance and answer quality
        confidence = _calculate_confidence(relevance_score, docs, answer)
        
        span.set_attribute("answer_length", len(answer))
        span.set_attribute("confidence", confidence)
        
        return {
            "answer": answer,
            "sources": sources,
            "confidence": confidence
        }


def generate_response_fast(state: AgentState) -> dict:
    """
    Node: Fast response generation for simple queries.
    
    Uses faster model with shorter prompt.
    """
    with tracer.start_as_current_span("fast_generator_node") as span:
        question = state["question"]
        docs = state.get("reranked_docs", [])
        
        # Shorter context for fast path
        context = _build_context(docs[:3], max_chars=1500)
        sources = _extract_sources(docs[:3])
        
        llm = GroqClient()
        answer = llm.generate(
            FAST_GENERATOR_PROMPT.format(question=question, context=context),
            model="llama-3.1-8b-instant",  # Fast model
            max_tokens=512
        )
        
        return {
            "answer": answer,
            "sources": sources,
            "confidence": 0.7  # Default confidence for fast path
        }


async def generate_response_stream(state: AgentState) -> AsyncGenerator[str, None]:
    """
    Stream response generation for better perceived latency.
    """
    question = state["question"]
    docs = state.get("reranked_docs", [])
    
    context = _build_context(docs)
    
    llm = GroqClient()
    async for chunk in llm.astream(
        GENERATOR_PROMPT.format(question=question, context=context),
        model="llama-3.3-70b-versatile"
    ):
        yield chunk


def _build_context(docs: List[dict], max_chars: int = 4000) -> str:
    """Build context string from documents"""
    context_parts = []
    total_chars = 0
    
    for i, doc in enumerate(docs):
        content = doc.get("content", "")
        source = doc.get("source", "unknown")
        
        part = f"[Document {i+1}: {source}]\n{content}\n"
        
        if total_chars + len(part) > max_chars:
            break
        
        context_parts.append(part)
        total_chars += len(part)
    
    return "\n".join(context_parts)


def _extract_sources(docs: List[dict]) -> List[str]:
    """Extract unique source names"""
    sources = []
    seen = set()
    
    for doc in docs:
        source = doc.get("source", "unknown")
        if source not in seen:
            sources.append(source)
            seen.add(source)
    
    return sources


def _calculate_confidence(relevance: float, docs: List[dict], answer: str) -> float:
    """Calculate overall confidence score"""
    # Base confidence from relevance
    confidence = relevance * 0.5
    
    # Boost if we have multiple sources
    if len(docs) >= 3:
        confidence += 0.15
    
    # Boost if answer is substantive
    if len(answer) > 100:
        confidence += 0.1
    
    # Penalty if answer seems uncertain
    uncertainty_phrases = ["i'm not sure", "unclear", "cannot determine", "no information"]
    for phrase in uncertainty_phrases:
        if phrase in answer.lower():
            confidence -= 0.2
    
    return max(0.0, min(1.0, confidence + 0.25))  # Ensure 0-1 range
