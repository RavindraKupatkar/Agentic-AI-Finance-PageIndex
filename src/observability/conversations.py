"""
Conversation History Service — Stateless Proxy to Convex

Instead of storing data locally in SQLite, this module now acts as a
stateless proxy, relaying conversation CRUD operations to the 
Convex cloud backend via convex_service.
"""

from __future__ import annotations

from typing import Any, Optional
from pathlib import Path

from ..core.config import settings
from .logging import get_logger
from ..services.convex_service import convex_service

logger = get_logger(__name__)


class ConversationService:
    """Async stateless proxy for conversation persistence via Convex."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self._initialized: bool = True
        logger.info("Stateless Conversation Service connected to Convex.")

    async def initialize(self) -> None:
        """No-op for backwards compatibility."""
        pass

    # ─── Conversation CRUD ─────────────────────────────

    async def create_conversation(self, title: str = "New Conversation") -> str:
        try:
            return convex_service.create_conversation(title=title)
        except Exception as exc:
            logger.error("conversations.create_failed", error=str(exc))
            return ""

    async def list_conversations(self, limit: int = 50) -> list[dict]:
        try:
            raw_convs = convex_service.list_conversations()
            # Map Convex document format to expected format
            result = []
            for c in raw_convs[:limit]:
                result.append({
                    "id": c["_id"],
                    "title": c["title"],
                    "created_at": c["createdAt"],
                    "updated_at": c["updatedAt"],
                    "message_count": 0, # Optimization: avoid fetching all messages just for count
                    "documents": c.get("documentIds", []),
                })
            return result
        except Exception as exc:
            logger.error("conversations.list_failed", error=str(exc))
            return []

    async def get_conversation(self, conv_id: str) -> Optional[dict]:
        try:
            conv = convex_service.get_conversation(conv_id)
            if not conv:
                return None

            raw_messages = convex_service.get_conversation_messages(conv_id)
            messages = []
            for m in raw_messages:
                messages.append({
                    "id": m["_id"],
                    "role": m["role"],
                    "content": m["content"],
                    "sources": m.get("sources"),
                    "confidence": m.get("confidence"),
                    "latency_ms": m.get("latencyMs"),
                    "created_at": m["createdAt"],
                })

            return {
                "id": conv["_id"],
                "title": conv["title"],
                "created_at": conv["createdAt"],
                "updated_at": conv["updatedAt"],
                "messages": messages,
                "documents": [{"doc_id": doc_id} for doc_id in conv.get("documentIds", [])],
            }
        except Exception as exc:
            logger.error("conversations.get_failed", error=str(exc))
            return None

    async def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        sources: Optional[list] = None,
        confidence: Optional[float] = None,
        latency_ms: Optional[float] = None,
    ) -> int:
        try:
            if role == "assistant":
                msg_id = convex_service.save_agent_response(
                    conversation_id=conv_id,
                    content=content,
                    sources=sources,
                    confidence=confidence,
                    latency_ms=latency_ms
                )
            else:
                # the sendMessage mutation expects conversationId and content
                msg_id = convex_service.client.mutation("messages:sendMessage", {
                    "conversationId": conv_id,
                    "content": content
                })
            return 1 # Return a positive integer to signify success (originally sqlite lastrowid)
        except Exception as exc:
            logger.error("conversations.add_message_failed", error=str(exc))
            return -1

    async def attach_document(
        self,
        conv_id: str,
        doc_id: str,
        filename: str,
        total_pages: int = 0,
    ) -> None:
        try:
            convex_service.attach_document_to_conversation(conv_id, doc_id)
        except Exception as exc:
            logger.error("conversations.attach_doc_failed", error=str(exc))

    async def delete_conversation(self, conv_id: str) -> bool:
        try:
            convex_service.delete_conversation(conv_id)
            return True
        except Exception as exc:
            logger.error("conversations.delete_failed", error=str(exc))
            return False


# ──────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────

_conversation_instance: Optional[ConversationService] = None

async def get_conversation_service() -> ConversationService:
    global _conversation_instance
    if _conversation_instance is None:
        _conversation_instance = ConversationService()
        await _conversation_instance.initialize()
    return _conversation_instance
