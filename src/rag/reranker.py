"""
Cross-Encoder Reranker - Improve retrieval precision

Uses cross-encoder models to rerank initial retrieval results.
"""

from typing import List, Dict, Any, Optional

from ..core.config import settings


class CrossEncoderReranker:
    """
    Rerank documents using a cross-encoder model.
    
    Cross-encoders are more accurate than bi-encoders for ranking.
    """
    
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if CrossEncoderReranker._model is None:
            try:
                from sentence_transformers import CrossEncoder
                
                CrossEncoderReranker._model = CrossEncoder(
                    settings.reranker_model,
                    max_length=512
                )
            except ImportError:
                # Fallback: no reranking
                CrossEncoderReranker._model = None
    
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents by relevance to query.
        
        Args:
            query: Search query
            documents: Documents to rerank
            top_k: Number of top documents to return
            
        Returns:
            Reranked documents with updated scores
        """
        if not documents:
            return []
        
        if CrossEncoderReranker._model is None:
            # No reranker available, return as-is
            return documents[:top_k]
        
        # Prepare pairs for cross-encoder
        pairs = [
            (query, doc.get("content", "")[:512])
            for doc in documents
        ]
        
        # Get reranker scores
        scores = CrossEncoderReranker._model.predict(pairs)
        
        # Combine with original documents
        scored_docs = list(zip(documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        # Update scores and return top_k
        result = []
        for doc, score in scored_docs[:top_k]:
            doc_copy = doc.copy()
            doc_copy["rerank_score"] = float(score)
            doc_copy["score"] = float(score)  # Replace original score
            result.append(doc_copy)
        
        return result
