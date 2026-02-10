"""
Hybrid Retriever - Vector + Keyword Search

Combines semantic vector search with BM25 keyword search.
"""

from typing import List, Dict, Any

from .embeddings import EmbeddingService
from ..vectorstore.qdrant_store import QdrantStore


class HybridRetriever:
    """
    Hybrid retrieval combining vector and keyword search.
    
    Uses Reciprocal Rank Fusion (RRF) to combine results.
    """
    
    def __init__(self, collection_name: str = "finance_docs"):
        self.embedding_service = EmbeddingService()
        self.vector_store = QdrantStore(collection_name=collection_name)
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search.
        
        Args:
            query: Search query
            top_k: Number of results to return
            vector_weight: Weight for vector search results
            keyword_weight: Weight for keyword search results
            
        Returns:
            List of documents with scores
        """
        # Generate query embedding
        query_embedding = self.embedding_service.embed_query(query)
        
        # Vector search
        vector_results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k * 2  # Over-fetch for hybrid fusion
        )
        
        # For now, just return vector results
        # TODO: Add BM25 keyword search and RRF fusion
        
        return vector_results[:top_k]
    
    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict],
        keyword_results: List[Dict],
        k: int = 60
    ) -> List[Dict]:
        """
        Combine results using Reciprocal Rank Fusion.
        
        RRF score = sum(1 / (k + rank))
        """
        scores = {}
        
        # Score vector results
        for rank, doc in enumerate(vector_results):
            doc_id = doc.get("id", str(rank))
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
            scores[f"{doc_id}_doc"] = doc
        
        # Score keyword results
        for rank, doc in enumerate(keyword_results):
            doc_id = doc.get("id", str(rank))
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
            if f"{doc_id}_doc" not in scores:
                scores[f"{doc_id}_doc"] = doc
        
        # Sort by combined score
        doc_scores = [
            (doc_id, score) 
            for doc_id, score in scores.items() 
            if not doc_id.endswith("_doc")
        ]
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return documents in ranked order
        return [scores.get(f"{doc_id}_doc") for doc_id, _ in doc_scores]
