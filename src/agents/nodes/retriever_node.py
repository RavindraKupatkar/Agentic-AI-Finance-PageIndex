"""
Retriever Node - Hybrid Search and Reranking

Handles vector search, BM25 keyword search, and cross-encoder reranking.
"""

from typing import List

from ..schemas.state import AgentState, RetrievedDocument
from ...rag.embeddings import EmbeddingService
from ...vectorstore.qdrant_store import QdrantStore
from ...rag.reranker import CrossEncoderReranker
from ...observability.tracing import tracer
from ...observability.metrics import RETRIEVAL_LATENCY, RETRIEVAL_COUNT


def retrieve_and_rerank(state: AgentState) -> dict:
    """
    Node: Retrieve documents using hybrid search and rerank.
    
    Input: question, (optional) plan, current_step
    Output: query_embedding, retrieved_docs, reranked_docs, retry_count
    """
    with tracer.start_as_current_span("retriever_node") as span:
        question = state["question"]
        retry_count = state.get("retry_count", 0)
        
        # Check if we have a plan and should use sub-query
        plan = state.get("plan")
        current_step = state.get("current_step", 0)
        
        if plan and current_step < len(plan):
            search_query = plan[current_step].get("query", question)
        else:
            search_query = question
        
        span.set_attribute("search_query", search_query[:100])
        span.set_attribute("retry_count", retry_count)
        
        # Step 1: Generate embedding
        with tracer.start_as_current_span("embed_query"):
            embedding_service = EmbeddingService()
            query_embedding = embedding_service.embed_text(search_query)
        
        # Step 2: Vector search
        with tracer.start_as_current_span("vector_search"):
            store = QdrantStore()
            raw_results = store.search(
                query_embedding=query_embedding,
                top_k=20,  # Over-fetch for reranking
                score_threshold=0.3
            )
        
        span.set_attribute("raw_results_count", len(raw_results))
        RETRIEVAL_COUNT.inc()
        
        # Step 3: Rerank with cross-encoder
        with tracer.start_as_current_span("rerank"):
            reranker = CrossEncoderReranker()
            reranked = reranker.rerank(
                query=search_query,
                documents=raw_results,
                top_k=5  # Final context size
            )
        
        span.set_attribute("reranked_count", len(reranked))
        
        # Convert to serializable format
        retrieved_docs = [
            {
                "id": doc.get("id", ""),
                "content": doc.get("content", ""),
                "source": doc.get("source", "unknown"),
                "score": doc.get("score", 0.0),
                "metadata": doc.get("metadata", {})
            }
            for doc in raw_results
        ]
        
        reranked_docs = [
            {
                "id": doc.get("id", ""),
                "content": doc.get("content", ""),
                "source": doc.get("source", "unknown"),
                "score": doc.get("score", 0.0),
                "metadata": doc.get("metadata", {})
            }
            for doc in reranked
        ]
        
        return {
            "query_embedding": query_embedding,
            "retrieved_docs": retrieved_docs,
            "reranked_docs": reranked_docs,
            "retry_count": retry_count
        }
