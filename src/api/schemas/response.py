"""API Schemas - Response Models"""
from pydantic import BaseModel, Field
from typing import List, Optional


class QueryResponse(BaseModel):
    """Response model for RAG queries"""
    answer: str = Field(..., description="Generated answer")
    sources: List[str] = Field(default_factory=list, description="Source documents")
    confidence: float = Field(ge=0, le=1, description="Confidence score")
    latency_ms: float = Field(..., description="Response latency in milliseconds")


class StreamChunk(BaseModel):
    """Streaming response chunk"""
    content: str
    done: bool = False
    sources: Optional[List[str]] = None


class IngestResponse(BaseModel):
    """Response model for document ingestion"""
    filename: str
    chunks_created: int
    status: str
    message: str


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None
