"""
Telemetry Service — Async SQLite-based Observability for PageIndex RAG

Provides structured logging of the full query lifecycle into telemetry.db.
Replaces OTLP/OpenTelemetry for the development phase; designed to be
swapped with a distributed telemetry backend in production later.

Tables:
    query_logs       — Full query lifecycle (start → each node → result)
    node_executions  — Per-node timing, I/O summaries, and status
    llm_calls        — Every LLM API call with token counts and latency
    errors           — Structured error log with recovery actions

Design decisions:
    - Fully async via aiosqlite (non-blocking in FastAPI/LangGraph)
    - WAL mode for concurrent read safety
    - Parameterized queries only (SQL injection prevention)
    - Singleton pattern to avoid connection churn
    - Graceful degradation: telemetry failures never crash the pipeline
"""

from __future__ import annotations

import json
import traceback
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

_CREATE_QUERY_LOGS = """
CREATE TABLE IF NOT EXISTS query_logs (
    id               TEXT PRIMARY KEY,
    thread_id        TEXT NOT NULL,
    user_id          TEXT,
    question         TEXT NOT NULL,
    query_type       TEXT,
    answer           TEXT,
    sources          TEXT,
    confidence       REAL,
    total_latency_ms REAL,
    status           TEXT NOT NULL DEFAULT 'started',
    error            TEXT,
    created_at       TEXT NOT NULL,
    completed_at     TEXT
);
"""

_CREATE_NODE_EXECUTIONS = """
CREATE TABLE IF NOT EXISTS node_executions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id        TEXT NOT NULL,
    node_name       TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    duration_ms     REAL,
    input_summary   TEXT,
    output_summary  TEXT,
    status          TEXT NOT NULL DEFAULT 'running',
    error           TEXT,
    FOREIGN KEY (query_id) REFERENCES query_logs(id)
);
"""

_CREATE_LLM_CALLS = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id          TEXT,
    node_name         TEXT,
    model             TEXT NOT NULL,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    latency_ms        REAL,
    temperature       REAL,
    status            TEXT NOT NULL DEFAULT 'success',
    error             TEXT,
    created_at        TEXT NOT NULL,
    FOREIGN KEY (query_id) REFERENCES query_logs(id)
);
"""

_CREATE_ERRORS = """
CREATE TABLE IF NOT EXISTS errors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id        TEXT,
    node_name       TEXT,
    error_type      TEXT NOT NULL,
    error_message   TEXT NOT NULL,
    stack_trace     TEXT,
    recovery_action TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (query_id) REFERENCES query_logs(id)
);
"""

_ALL_SCHEMAS = [
    _CREATE_QUERY_LOGS,
    _CREATE_NODE_EXECUTIONS,
    _CREATE_LLM_CALLS,
    _CREATE_ERRORS,
]


def _now_iso() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _generate_query_id() -> str:
    """Generate a unique query ID."""
    return str(uuid.uuid4())


def _safe_json(obj: Any) -> Optional[str]:
    """Safely serialize an object to JSON string.

    Args:
        obj: Object to serialize.

    Returns:
        JSON string or None if serialization fails.
    """
    if obj is None:
        return None
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(obj)


# ──────────────────────────────────────────────────────────────
# Core Service
# ──────────────────────────────────────────────────────────────


class TelemetryService:
    """
    Async SQLite telemetry service for the PageIndex RAG pipeline.

    Records the full lifecycle of every query: which nodes ran,
    how long they took, what LLM calls were made, and any errors.

    All public methods are designed to never raise exceptions —
    telemetry failures are logged but never crash the pipeline.

    Usage (injected via InjectedState):
        telemetry = TelemetryService()
        await telemetry.initialize()
        query_id = await telemetry.start_query(question="...", thread_id="...")
        await telemetry.log_node_start(query_id, "router")
        await telemetry.log_node_end(query_id, "router", output={"query_type": "standard"})
        await telemetry.complete_query(query_id, answer="...", confidence=0.9)

    Attributes:
        db_path: Absolute path to the SQLite telemetry database.
    """

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        """
        Initialize TelemetryService.

        Args:
            db_path: Path to the telemetry SQLite database.
                     Defaults to settings.telemetry_db_absolute.
        """
        self.db_path: str = str(
            Path(db_path).resolve() if db_path else settings.telemetry_db_absolute
        )
        self._initialized: bool = False

    async def initialize(self) -> None:
        """
        Initialize the database schema.

        Creates the telemetry.db file and all 4 tables if they
        don't exist. Enables WAL mode for concurrent read safety.

        Raises:
            No exceptions — logs errors and sets _initialized=False.
        """
        try:
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL;")
                for schema in _ALL_SCHEMAS:
                    await db.execute(schema)
                await db.commit()

            self._initialized = True
            logger.info(
                "telemetry.initialized",
                db_path=self.db_path,
                tables=["query_logs", "node_executions", "llm_calls", "errors"],
            )
        except Exception as exc:
            logger.error(
                "telemetry.init_failed",
                error=str(exc),
                db_path=self.db_path,
            )
            self._initialized = False

    # ─── Query Lifecycle ───────────────────────────────

    async def start_query(
        self,
        question: str,
        thread_id: str = "default",
        user_id: Optional[str] = None,
    ) -> str:
        """
        Record the start of a new query.

        Args:
            question: The user's question text.
            thread_id: Conversation thread identifier.
            user_id: Optional user identifier.

        Returns:
            Unique query_id (UUID string) for tracking this query.
        """
        query_id = _generate_query_id()

        await self._execute_write(
            """
            INSERT INTO query_logs (id, thread_id, user_id, question, status, created_at)
            VALUES (?, ?, ?, ?, 'started', ?)
            """,
            (query_id, thread_id, user_id, question, _now_iso()),
        )

        logger.info(
            "telemetry.query_started",
            query_id=query_id,
            thread_id=thread_id,
            question_length=len(question),
        )

        return query_id

    async def complete_query(
        self,
        query_id: str,
        answer: Optional[str] = None,
        sources: Optional[list] = None,
        confidence: Optional[float] = None,
        query_type: Optional[str] = None,
        total_latency_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Record the completion of a query.

        Args:
            query_id: The query ID from start_query().
            answer: Generated answer text.
            sources: List of source citations.
            confidence: Overall confidence score (0.0-1.0).
            query_type: Classified query type (simple/standard/complex/multi_hop).
            total_latency_ms: Total time from start to completion.
            error: Error message if the query failed.
        """
        status = "failed" if error else "completed"

        await self._execute_write(
            """
            UPDATE query_logs
            SET answer = ?, sources = ?, confidence = ?, query_type = ?,
                total_latency_ms = ?, status = ?, error = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                answer,
                _safe_json(sources),
                confidence,
                query_type,
                total_latency_ms,
                status,
                error,
                _now_iso(),
                query_id,
            ),
        )

        logger.info(
            "telemetry.query_completed",
            query_id=query_id,
            status=status,
            confidence=confidence,
            latency_ms=total_latency_ms,
        )

    # ─── Node Execution Tracking ───────────────────────

    async def log_node_start(
        self,
        query_id: str,
        node_name: str,
        input_summary: Optional[dict] = None,
    ) -> int:
        """
        Record the start of a node execution.

        Args:
            query_id: Parent query ID.
            node_name: Name of the LangGraph node (e.g., "router", "tree_search").
            input_summary: Key fields from the state entering this node.

        Returns:
            Row ID of the node execution record (for log_node_end).
        """
        row_id = await self._execute_write_returning_id(
            """
            INSERT INTO node_executions
                (query_id, node_name, started_at, input_summary, status)
            VALUES (?, ?, ?, ?, 'running')
            """,
            (query_id, node_name, _now_iso(), _safe_json(input_summary)),
        )

        logger.debug(
            "telemetry.node_started",
            query_id=query_id,
            node_name=node_name,
        )

        return row_id

    async def log_node_end(
        self,
        node_execution_id: int,
        query_id: str,
        node_name: str,
        output_summary: Optional[dict] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Record the completion of a node execution.

        Args:
            node_execution_id: Row ID from log_node_start().
            query_id: Parent query ID.
            node_name: Name of the LangGraph node.
            output_summary: Key fields produced by this node.
            duration_ms: Node execution time in milliseconds.
            error: Error message if the node failed.
        """
        status = "failed" if error else "completed"

        await self._execute_write(
            """
            UPDATE node_executions
            SET completed_at = ?, duration_ms = ?, output_summary = ?,
                status = ?, error = ?
            WHERE id = ?
            """,
            (
                _now_iso(),
                duration_ms,
                _safe_json(output_summary),
                status,
                error,
                node_execution_id,
            ),
        )

        logger.debug(
            "telemetry.node_completed",
            query_id=query_id,
            node_name=node_name,
            duration_ms=duration_ms,
            status=status,
        )

    # ─── LLM Call Tracking ─────────────────────────────

    async def log_llm_call(
        self,
        query_id: Optional[str],
        node_name: Optional[str],
        model: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        latency_ms: Optional[float] = None,
        temperature: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Record an LLM API call.

        Args:
            query_id: Parent query ID (None for standalone calls).
            node_name: Node that initiated the call.
            model: LLM model name (e.g., "llama-3.3-70b-versatile").
            prompt_tokens: Number of prompt/input tokens.
            completion_tokens: Number of completion/output tokens.
            total_tokens: Total token count.
            latency_ms: API call latency in milliseconds.
            temperature: Sampling temperature used.
            error: Error message if the call failed.
        """
        status = "failed" if error else "success"

        await self._execute_write(
            """
            INSERT INTO llm_calls
                (query_id, node_name, model, prompt_tokens, completion_tokens,
                 total_tokens, latency_ms, temperature, status, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query_id,
                node_name,
                model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                latency_ms,
                temperature,
                status,
                error,
                _now_iso(),
            ),
        )

        logger.debug(
            "telemetry.llm_call",
            query_id=query_id,
            node_name=node_name,
            model=model,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            status=status,
        )

    # ─── Error Logging ─────────────────────────────────

    async def log_error(
        self,
        error_type: str,
        error_message: str,
        query_id: Optional[str] = None,
        node_name: Optional[str] = None,
        exception: Optional[Exception] = None,
        recovery_action: Optional[str] = None,
    ) -> None:
        """
        Record a structured error.

        Args:
            error_type: Category of error (e.g., "LLMError", "ValidationError").
            error_message: Human-readable error description.
            query_id: Parent query ID if within a query context.
            node_name: Node where the error occurred.
            exception: Original exception object for stack trace extraction.
            recovery_action: What the system did after the error
                             (e.g., "retry", "fallback", "abort").
        """
        stack_trace = None
        if exception:
            stack_trace = "".join(
                traceback.format_exception(type(exception), exception, exception.__traceback__)
            )

        await self._execute_write(
            """
            INSERT INTO errors
                (query_id, node_name, error_type, error_message,
                 stack_trace, recovery_action, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query_id,
                node_name,
                error_type,
                error_message,
                stack_trace,
                recovery_action,
                _now_iso(),
            ),
        )

        logger.error(
            "telemetry.error_logged",
            error_type=error_type,
            error_message=error_message,
            query_id=query_id,
            node_name=node_name,
            recovery_action=recovery_action,
        )

    # ─── Query Methods (for Admin/Debug) ───────────────

    async def get_query_log(self, query_id: str) -> Optional[dict]:
        """
        Retrieve a single query log by ID.

        Args:
            query_id: The query UUID.

        Returns:
            Dict with query log fields, or None if not found.
        """
        row = await self._execute_read_one(
            "SELECT * FROM query_logs WHERE id = ?", (query_id,)
        )
        if row is None:
            return None

        return {
            "id": row[0],
            "thread_id": row[1],
            "user_id": row[2],
            "question": row[3],
            "query_type": row[4],
            "answer": row[5],
            "sources": json.loads(row[6]) if row[6] else None,
            "confidence": row[7],
            "total_latency_ms": row[8],
            "status": row[9],
            "error": row[10],
            "created_at": row[11],
            "completed_at": row[12],
        }

    async def get_node_executions(self, query_id: str) -> list[dict]:
        """
        Get all node executions for a query.

        Args:
            query_id: The query UUID.

        Returns:
            List of node execution dicts ordered by start time.
        """
        rows = await self._execute_read_all(
            """
            SELECT id, query_id, node_name, started_at, completed_at,
                   duration_ms, input_summary, output_summary, status, error
            FROM node_executions
            WHERE query_id = ?
            ORDER BY started_at ASC
            """,
            (query_id,),
        )

        return [
            {
                "id": row[0],
                "query_id": row[1],
                "node_name": row[2],
                "started_at": row[3],
                "completed_at": row[4],
                "duration_ms": row[5],
                "input_summary": json.loads(row[6]) if row[6] else None,
                "output_summary": json.loads(row[7]) if row[7] else None,
                "status": row[8],
                "error": row[9],
            }
            for row in rows
        ]

    async def get_recent_queries(self, limit: int = 20) -> list[dict]:
        """
        Get the most recent queries.

        Args:
            limit: Maximum number of queries to return (default 20).

        Returns:
            List of query log dicts ordered by creation time descending.
        """
        rows = await self._execute_read_all(
            """
            SELECT id, thread_id, question, query_type, confidence,
                   total_latency_ms, status, created_at
            FROM query_logs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

        return [
            {
                "id": row[0],
                "thread_id": row[1],
                "question": row[2],
                "query_type": row[3],
                "confidence": row[4],
                "total_latency_ms": row[5],
                "status": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]

    async def get_llm_calls(self, query_id: str) -> list[dict]:
        """
        Get all LLM calls for a query.

        Args:
            query_id: The query UUID.

        Returns:
            List of LLM call dicts.
        """
        rows = await self._execute_read_all(
            """
            SELECT id, query_id, node_name, model, prompt_tokens,
                   completion_tokens, total_tokens, latency_ms,
                   temperature, status, error, created_at
            FROM llm_calls
            WHERE query_id = ?
            ORDER BY created_at ASC
            """,
            (query_id,),
        )

        return [
            {
                "id": row[0],
                "query_id": row[1],
                "node_name": row[2],
                "model": row[3],
                "prompt_tokens": row[4],
                "completion_tokens": row[5],
                "total_tokens": row[6],
                "latency_ms": row[7],
                "temperature": row[8],
                "status": row[9],
                "error": row[10],
                "created_at": row[11],
            }
            for row in rows
        ]

    async def get_errors(
        self, query_id: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """
        Get error records, optionally filtered by query_id.

        Args:
            query_id: Filter by query ID. None returns all errors.
            limit: Maximum number of errors to return.

        Returns:
            List of error dicts ordered by creation time descending.
        """
        if query_id:
            sql = """
                SELECT id, query_id, node_name, error_type, error_message,
                       stack_trace, recovery_action, created_at
                FROM errors
                WHERE query_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (query_id, limit)
        else:
            sql = """
                SELECT id, query_id, node_name, error_type, error_message,
                       stack_trace, recovery_action, created_at
                FROM errors
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (limit,)

        rows = await self._execute_read_all(sql, params)

        return [
            {
                "id": row[0],
                "query_id": row[1],
                "node_name": row[2],
                "error_type": row[3],
                "error_message": row[4],
                "stack_trace": row[5],
                "recovery_action": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]

    async def get_table_counts(self) -> dict[str, int]:
        """
        Get row counts for all telemetry tables.

        Returns:
            Dict mapping table name to row count.
        """
        counts: dict[str, int] = {}
        for table in ("query_logs", "node_executions", "llm_calls", "errors"):
            rows = await self._execute_read_all(
                f"SELECT COUNT(*) FROM [{table}]"
            )
            counts[table] = rows[0][0] if rows else 0
        return counts

    # ─── Private: Database operations ──────────────────

    async def _execute_write(self, sql: str, params: tuple = ()) -> None:
        """
        Execute a write SQL statement.

        Silently logs errors — telemetry failures never crash the pipeline.

        Args:
            sql: SQL statement with ? placeholders.
            params: Tuple of parameter values.
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(sql, params)
                await db.commit()
        except Exception as exc:
            logger.warning(
                "telemetry.write_failed",
                error=str(exc),
                sql=sql[:100],
            )

    async def _execute_write_returning_id(
        self, sql: str, params: tuple = ()
    ) -> int:
        """
        Execute a write SQL statement and return the last inserted row ID.

        Args:
            sql: SQL INSERT statement with ? placeholders.
            params: Tuple of parameter values.

        Returns:
            Last inserted row ID, or -1 on failure.
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(sql, params)
                await db.commit()
                return cursor.lastrowid or -1
        except Exception as exc:
            logger.warning(
                "telemetry.write_returning_id_failed",
                error=str(exc),
                sql=sql[:100],
            )
            return -1

    async def _execute_read_one(
        self, sql: str, params: tuple = ()
    ) -> Optional[tuple]:
        """
        Execute a read SQL statement and return one row.

        Args:
            sql: SQL SELECT statement with ? placeholders.
            params: Tuple of parameter values.

        Returns:
            Single result row or None.
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(sql, params)
                return await cursor.fetchone()
        except Exception as exc:
            logger.warning(
                "telemetry.read_one_failed",
                error=str(exc),
                sql=sql[:100],
            )
            return None

    async def _execute_read_all(
        self, sql: str, params: tuple = ()
    ) -> list[tuple]:
        """
        Execute a read SQL statement and return all rows.

        Args:
            sql: SQL SELECT statement with ? placeholders.
            params: Tuple of parameter values.

        Returns:
            List of result rows.
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(sql, params)
                return await cursor.fetchall()
        except Exception as exc:
            logger.warning(
                "telemetry.read_all_failed",
                error=str(exc),
                sql=sql[:100],
            )
            return []


# ──────────────────────────────────────────────────────────────
# Singleton factory
# ──────────────────────────────────────────────────────────────

_telemetry_instance: Optional[TelemetryService] = None


async def get_telemetry_service() -> TelemetryService:
    """
    Get or create the global TelemetryService singleton.

    Returns:
        Initialized TelemetryService instance.
    """
    global _telemetry_instance

    if _telemetry_instance is None:
        _telemetry_instance = TelemetryService()
        await _telemetry_instance.initialize()

    return _telemetry_instance
