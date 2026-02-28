"""
Telemetry Service — Stateless Convex-based Observability

Provides structured logging of the full query lifecycle into Convex.
All data is stored in the remote cloud database, zero local data.
"""

import time
import uuid
from typing import Optional, Any

from src.observability.logging import get_logger
from src.services.convex_service import convex_service

logger = get_logger(__name__)

def _generate_query_id() -> str:
    """Generate a unique query ID."""
    return f"req_{uuid.uuid4().hex[:12]}"

class TelemetryService:
    """Stateless telemetry proxy sending logs straight to Convex."""
    
    def __init__(self, db_path=None):
        self._initialized = True
        logger.info("Stateless Telemetry Service connected to Convex.")

    async def initialize(self):
        """No-op for convex."""
        pass

    async def start_query(
        self,
        question: str,
        thread_id: str = "default",
        user_id: Optional[str] = None,
    ) -> str:
        query_id = _generate_query_id()
        try:
            convex_service.log_event(
                event_type="query_start",
                query_id=query_id,
                details={"question": question, "thread_id": thread_id, "user_id": user_id}
            )
        except Exception as e:
            logger.warning("Telemetry log failed", error=str(e))
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
    ):
        try:
            convex_service.log_event(
                event_type="query_complete",
                query_id=query_id,
                duration_ms=total_latency_ms,
                details={
                    "answer": answer,
                    "sources": sources,
                    "confidence": confidence,
                    "query_type": query_type,
                    "error": error
                }
            )
        except Exception:
            pass

    async def log_node_start(self, query_id: str, node_name: str, input_summary: Optional[dict] = None) -> int:
        try:
            convex_service.log_event(
                event_type="node_start",
                query_id=query_id,
                node_name=node_name,
                details={"input": input_summary}
            )
        except Exception:
            pass
        return 0

    async def log_node_end(
        self,
        node_execution_id: int,
        query_id: str,
        node_name: str,
        output_summary: Optional[dict] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ):
        try:
            convex_service.log_event(
                event_type="node_end",
                query_id=query_id,
                node_name=node_name,
                duration_ms=duration_ms,
                details={"output": output_summary, "error": error}
            )
        except Exception:
            pass

    async def log_llm_call(
        self,
        query_id: Optional[str],
        node_name: Optional[str],
        model: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
        temperature: float = 0.0,
    ):
        try:
            convex_service.log_event(
                event_type="llm_call",
                query_id=query_id or "unknown",
                node_name=node_name or "unknown",
                duration_ms=duration_ms,
                details={
                    "model": model,
                    "tokens": total_tokens,
                    "error": error
                }
            )
        except Exception:
            pass

    async def log_error(
        self,
        error_type: str,
        error_message: str,
        query_id: Optional[str] = None,
        node_name: Optional[str] = None,
        exception: Optional[Exception] = None,
        recovery_action: Optional[str] = None,
    ):
        try:
            convex_service.log_event(
                event_type="error",
                query_id=query_id or "unknown",
                node_name=node_name,
                details={
                    "type": error_type,
                    "message": error_message,
                    "recovery": recovery_action
                }
            )
        except Exception:
            pass

    async def log_state_snapshot(
        self,
        session_id: str,
        query_id: str,
        node_name: str,
        data: Optional[dict] = None,
    ):
        """Log a state snapshot after a node executes (used by query graph logging wrapper)."""
        try:
            convex_service.log_event(
                event_type="state_snapshot",
                query_id=query_id,
                node_name=node_name,
                details={"session_id": session_id},
            )
        except Exception:
            pass

    async def log_conversation(self, session_id: str, user_id: Optional[str], user_message: str, agent_response: Optional[str], duration_ms: Optional[float], metadata: Optional[dict] = None):
        """Conversations are handled by the Convex conversations table directly, but this logs the turn."""
        pass

    async def get_recent_queries(self, limit: int = 50) -> list[dict]:
        return []

    async def get_query_log(self, query_id: str) -> Optional[dict]:
        return None

    async def get_node_executions(self, query_id: str) -> list[dict]:
        return []

    async def get_llm_calls(self, query_id: str) -> list[dict]:
        return []

    async def get_errors(self, query_id: str = None, limit: int = 50) -> list[dict]:
        return []

    async def get_system_metrics(self) -> dict:
        return {}


# Singleton
_telemetry_instance: Optional[TelemetryService] = None

async def get_telemetry_service() -> TelemetryService:
    global _telemetry_instance
    if _telemetry_instance is None:
        _telemetry_instance = TelemetryService()
        await _telemetry_instance.initialize()
    return _telemetry_instance
