"""
Qdrant Vector Store - Production-grade vector database

Uses Qdrant for scalable, persistent vector storage.
"""

from typing import List, Dict, Any, Optional
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)

from ..core.config import settings


class QdrantStore:
    """
    Qdrant vector store for document embeddings.
    
    Supports both local (embedded) and remote Qdrant instances.
    """
    
    def __init__(self, collection_name: str = None):
        self.collection_name = collection_name or settings.collection_name
        
        # Connect to Qdrant
        if settings.qdrant_url:
            self.client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key
            )
        else:
            # Local embedded mode
            self.client = QdrantClient(path=settings.qdrant_path)
        
        # Ensure collection exists
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=settings.embedding_dimension,
                    distance=Distance.COSINE
                )
            )
    
    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> List[str]:
        """
        Add documents with embeddings to the store.
        
        Args:
            documents: List of document dicts with 'content', 'source', etc.
            embeddings: Corresponding embeddings
            
        Returns:
            List of document IDs
        """
        points = []
        ids = []
        
        for doc, embedding in zip(documents, embeddings):
            doc_id = str(uuid.uuid4())
            ids.append(doc_id)
            
            points.append(PointStruct(
                id=doc_id,
                vector=embedding,
                payload={
                    "content": doc.get("content", ""),
                    "source": doc.get("source", "unknown"),
                    "chunk_index": doc.get("chunk_index", 0),
                    "metadata": doc.get("metadata", {})
                }
            ))
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        return ids
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        score_threshold: float = 0.0,
        filter_source: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results
            score_threshold: Minimum similarity score
            filter_source: Optional source filter
            
        Returns:
            List of matching documents with scores
        """
        # Build filter if needed
        query_filter = None
        if filter_source:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="source",
                        match=MatchValue(value=filter_source)
                    )
                ]
            )
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=query_filter
        )
        
        return [
            {
                "id": str(result.id),
                "content": result.payload.get("content", ""),
                "source": result.payload.get("source", "unknown"),
                "chunk_index": result.payload.get("chunk_index", 0),
                "score": result.score,
                "metadata": result.payload.get("metadata", {})
            }
            for result in results
        ]
    
    def get_count(self) -> int:
        """Get number of documents in collection"""
        info = self.client.get_collection(self.collection_name)
        return info.points_count
    
    def clear(self):
        """Delete all documents from collection"""
        self.client.delete_collection(self.collection_name)
        self._ensure_collection()
    
    def health_check(self) -> bool:
        """Check if Qdrant is available"""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False
