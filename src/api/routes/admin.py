"""
Admin Routes - System administration endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class SystemStatus(BaseModel):
    document_count: int
    chunk_count: int
    index_status: str
    memory_usage_mb: float


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get system status and statistics"""
    from ...vectorstore.qdrant_store import QdrantStore
    
    store = QdrantStore()
    count = store.get_count()
    
    return SystemStatus(
        document_count=0,  # TODO: Track unique documents
        chunk_count=count,
        index_status="healthy",
        memory_usage_mb=0.0  # TODO: Implement memory tracking
    )


@router.delete("/clear")
async def clear_vector_store():
    """Clear all documents from vector store (USE WITH CAUTION)"""
    from ...vectorstore.qdrant_store import QdrantStore
    
    store = QdrantStore()
    store.clear()
    
    return {"status": "cleared", "message": "All documents removed"}


@router.post("/reindex")
async def reindex_documents():
    """Trigger reindexing of all documents"""
    # TODO: Implement reindexing
    return {"status": "started", "message": "Reindexing in progress"}
