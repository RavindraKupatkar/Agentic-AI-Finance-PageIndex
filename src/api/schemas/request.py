"""API Schemas - Request Models"""
from pydantic import BaseModel, Field
from typing import Optional


class QueryRequest(BaseModel):
    """Request model for RAG queries"""
    question: str = Field(..., min_length=1, max_length=2000, description="Question to ask")
    thread_id: str = Field(default="default", description="Conversation thread ID")
    user_id: Optional[str] = Field(default=None, description="User ID for tracking")
    stream: bool = Field(default=False, description="Enable streaming response")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "What is the company's revenue for Q4 2024?",
                    "thread_id": "user-123-session-1",
                    "stream": False
                }
            ]
        }
    }


class IngestRequest(BaseModel):
    """Request model for document ingestion"""
    chunk_size: int = Field(default=512, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=500)
    collection_name: Optional[str] = Field(default=None)
