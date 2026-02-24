"""
Conversation History Service — SQLite-based Chat Persistence

Stores conversations with messages, attached documents, and metadata.
Each conversation has a thread_id, list of messages, and document references.

Tables:
    conversations       — Thread metadata (id, title, created_at)
    conversation_messages — Individual messages with role, content, sources
    conversation_documents — Documents attached to a conversation
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from ..core.config import settings
from .logging import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# SQL Schema
# ──────────────────────────────────────────────────────────────

_CREATE_CONVERSATIONS = """
CREATE TABLE IF NOT EXISTS conversations (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL DEFAULT 'New Conversation',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
"""

_CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS conversation_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    sources         TEXT,
    confidence      REAL,
    latency_ms      REAL,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
"""

_CREATE_CONV_DOCS = """
CREATE TABLE IF NOT EXISTS conversation_documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    doc_id          TEXT NOT NULL,
    filename        TEXT NOT NULL,
    total_pages     INTEGER DEFAULT 0,
    attached_at     TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationService:
    """Async SQLite service for conversation persistence."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        resolved = Path(db_path).resolve() if db_path else settings.telemetry_db_absolute
        self.db_path: str = str(resolved).replace("telemetry.db", "conversations.db")
        self._initialized: bool = False

    async def initialize(self) -> None:
        try:
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL;")
                await db.execute(_CREATE_CONVERSATIONS)
                await db.execute(_CREATE_MESSAGES)
                await db.execute(_CREATE_CONV_DOCS)
                await db.commit()

            self._initialized = True
            logger.info("conversations.initialized", db_path=self.db_path)
        except Exception as exc:
            logger.error("conversations.init_failed", error=str(exc))
            self._initialized = False

    async def _ensure_init(self) -> None:
        if not self._initialized:
            await self.initialize()

    # ─── Conversation CRUD ─────────────────────────────

    async def create_conversation(self, title: str = "New Conversation") -> str:
        await self._ensure_init()
        conv_id = str(uuid.uuid4())
        now = _now_iso()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (conv_id, title, now, now),
                )
                await db.commit()
        except Exception as exc:
            logger.error("conversations.create_failed", error=str(exc))
        return conv_id

    async def list_conversations(self, limit: int = 50) -> list[dict]:
        await self._ensure_init()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    """
                    SELECT c.id, c.title, c.created_at, c.updated_at,
                           (SELECT COUNT(*) FROM conversation_messages WHERE conversation_id = c.id) as msg_count,
                           (SELECT content FROM conversation_messages WHERE conversation_id = c.id AND role = 'user' ORDER BY created_at ASC LIMIT 1) as first_question
                    FROM conversations c
                    ORDER BY c.updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                rows = await cursor.fetchall()
                
                result = []
                for row in rows:
                    # Get attached documents
                    doc_cursor = await db.execute(
                        "SELECT filename FROM conversation_documents WHERE conversation_id = ?",
                        (row[0],),
                    )
                    doc_rows = await doc_cursor.fetchall()
                    
                    result.append({
                        "id": row[0],
                        "title": row[1],
                        "created_at": row[2],
                        "updated_at": row[3],
                        "message_count": row[4],
                        "first_question": row[5],
                        "documents": [d[0] for d in doc_rows],
                    })
                return result
        except Exception as exc:
            logger.error("conversations.list_failed", error=str(exc))
            return []

    async def get_conversation(self, conv_id: str) -> Optional[dict]:
        await self._ensure_init()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get conversation
                cursor = await db.execute(
                    "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
                    (conv_id,),
                )
                conv = await cursor.fetchone()
                if not conv:
                    return None

                # Get messages
                msg_cursor = await db.execute(
                    """
                    SELECT id, role, content, sources, confidence, latency_ms, created_at
                    FROM conversation_messages
                    WHERE conversation_id = ?
                    ORDER BY created_at ASC
                    """,
                    (conv_id,),
                )
                messages = await msg_cursor.fetchall()

                # Get documents
                doc_cursor = await db.execute(
                    "SELECT doc_id, filename, total_pages, attached_at FROM conversation_documents WHERE conversation_id = ?",
                    (conv_id,),
                )
                docs = await doc_cursor.fetchall()

                return {
                    "id": conv[0],
                    "title": conv[1],
                    "created_at": conv[2],
                    "updated_at": conv[3],
                    "messages": [
                        {
                            "id": m[0],
                            "role": m[1],
                            "content": m[2],
                            "sources": json.loads(m[3]) if m[3] else None,
                            "confidence": m[4],
                            "latency_ms": m[5],
                            "created_at": m[6],
                        }
                        for m in messages
                    ],
                    "documents": [
                        {
                            "doc_id": d[0],
                            "filename": d[1],
                            "total_pages": d[2],
                            "attached_at": d[3],
                        }
                        for d in docs
                    ],
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
        await self._ensure_init()
        now = _now_iso()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    """
                    INSERT INTO conversation_messages
                        (conversation_id, role, content, sources, confidence, latency_ms, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (conv_id, role, content, json.dumps(sources) if sources else None, confidence, latency_ms, now),
                )
                # Update conversation timestamp and title from first user message
                await db.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conv_id),
                )
                # Auto-set title from first user message
                if role == "user":
                    await db.execute(
                        """
                        UPDATE conversations SET title = ?
                        WHERE id = ? AND title = 'New Conversation'
                        """,
                        (content[:80] + ("..." if len(content) > 80 else ""), conv_id),
                    )
                await db.commit()
                return cursor.lastrowid or -1
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
        await self._ensure_init()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO conversation_documents
                        (conversation_id, doc_id, filename, total_pages, attached_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (conv_id, doc_id, filename, total_pages, _now_iso()),
                )
                await db.commit()
        except Exception as exc:
            logger.error("conversations.attach_doc_failed", error=str(exc))

    async def delete_conversation(self, conv_id: str) -> bool:
        await self._ensure_init()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM conversation_messages WHERE conversation_id = ?", (conv_id,))
                await db.execute("DELETE FROM conversation_documents WHERE conversation_id = ?", (conv_id,))
                await db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
                await db.commit()
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
