"""
Conversation History API Routes

Provides CRUD endpoints for conversation persistence:
    - GET    /conversations           — List all conversations
    - POST   /conversations           — Create new conversation
    - GET    /conversations/{id}      — Get conversation with messages
    - POST   /conversations/{id}/message — Add a message
    - POST   /conversations/{id}/document — Attach a document
    - DELETE /conversations/{id}      — Delete a conversation
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...observability.conversations import get_conversation_service
from ...observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New Conversation")


class AddMessageRequest(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(...)
    sources: Optional[list] = None
    confidence: Optional[float] = None
    latency_ms: Optional[float] = None


class AttachDocumentRequest(BaseModel):
    doc_id: str = Field(...)
    filename: str = Field(...)
    total_pages: int = Field(default=0)


@router.get("")
async def list_conversations(limit: int = 50):
    service = await get_conversation_service()
    return await service.list_conversations(limit=limit)


@router.post("")
async def create_conversation(request: CreateConversationRequest):
    service = await get_conversation_service()
    conv_id = await service.create_conversation(title=request.title)
    return {"id": conv_id, "title": request.title}


@router.get("/{conv_id}")
async def get_conversation(conv_id: str):
    service = await get_conversation_service()
    conv = await service.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("/{conv_id}/message")
async def add_message(conv_id: str, request: AddMessageRequest):
    service = await get_conversation_service()
    msg_id = await service.add_message(
        conv_id=conv_id,
        role=request.role,
        content=request.content,
        sources=request.sources,
        confidence=request.confidence,
        latency_ms=request.latency_ms,
    )
    if msg_id == -1:
        raise HTTPException(status_code=500, detail="Failed to add message")
    return {"id": msg_id}


@router.post("/{conv_id}/document")
async def attach_document(conv_id: str, request: AttachDocumentRequest):
    service = await get_conversation_service()
    await service.attach_document(
        conv_id=conv_id,
        doc_id=request.doc_id,
        filename=request.filename,
        total_pages=request.total_pages,
    )
    return {"status": "attached"}


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str):
    service = await get_conversation_service()
    success = await service.delete_conversation(conv_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete conversation")
    return {"status": "deleted"}
