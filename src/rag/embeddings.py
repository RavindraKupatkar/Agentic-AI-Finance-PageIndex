"""
Embedding Service - Generate embeddings using BGE model

Uses BAAI/bge-base-en-v1.5 for high-quality embeddings.
"""

from typing import List
from sentence_transformers import SentenceTransformer

from ..core.config import settings


class EmbeddingService:
    """
    Singleton service for generating text embeddings.
    
    Uses bge-base-en-v1.5 (768 dimensions) for optimal quality/speed balance.
    """
    
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if EmbeddingService._model is None:
            model_name = settings.embedding_model
            device = "cuda" if settings.use_gpu else "cpu"
            
            EmbeddingService._model = SentenceTransformer(
                model_name,
                device=device
            )
    
    @property
    def model(self) -> SentenceTransformer:
        return EmbeddingService._model
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension"""
        return settings.embedding_dimension
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        embedding = self.model.encode(
            text,
            normalize_embeddings=True
        )
        return embedding.tolist()
    
    def embed_texts(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            show_progress: Show progress bar
            
        Returns:
            List of embedding vectors
        """
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=show_progress
        )
        return [emb.tolist() for emb in embeddings]
    
    def embed_query(self, query: str) -> List[float]:
        """
        Embed a query with instruction prefix (for bge models).
        
        BGE models perform better with an instruction prefix for queries.
        """
        # BGE models work better with instruction prefix
        instruction = "Represent this sentence for searching relevant passages: "
        return self.embed_text(instruction + query)
