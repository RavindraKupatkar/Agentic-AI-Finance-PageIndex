"""
Agent Orchestrator - Main Entry Point for RAG Queries

Provides high-level interface for processing queries through the agent graph.
"""

from typing import Optional, AsyncGenerator
from dataclasses import dataclass

from .graphs.query_graph import get_query_graph
from .schemas.state import create_initial_state, AgentState
from ..observability.tracing import tracer
from ..observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QueryResult:
    """Result from a RAG query"""
    answer: str
    sources: list
    confidence: float
    latency_ms: float = 0.0
    error: Optional[str] = None


class AgentOrchestrator:
    """
    Main orchestrator for the agentic RAG system.
    
    Provides sync and async interfaces for processing queries.
    """
    
    def __init__(self, persistent_memory: bool = False):
        """
        Initialize the orchestrator.
        
        Args:
            persistent_memory: Use SQLite for persistent conversation memory
        """
        self.graph = get_query_graph(persistent=persistent_memory)
        self.logger = logger
    
    def query(
        self,
        question: str,
        thread_id: str = "default",
        user_id: Optional[str] = None
    ) -> QueryResult:
        """
        Process a RAG query synchronously.
        
        Args:
            question: User's question
            thread_id: Conversation thread ID for memory
            user_id: Optional user identifier
            
        Returns:
            QueryResult with answer, sources, and confidence
        """
        import time
        start = time.time()
        
        with tracer.start_as_current_span("orchestrator_query") as span:
            span.set_attribute("thread_id", thread_id)
            span.set_attribute("question_length", len(question))
            
            try:
                # Create initial state
                initial_state = create_initial_state(
                    question=question,
                    thread_id=thread_id,
                    user_id=user_id
                )
                
                # Configure with thread_id for memory
                config = {"configurable": {"thread_id": thread_id}}
                
                # Run the graph
                result = self.graph.invoke(initial_state, config)
                
                latency = (time.time() - start) * 1000
                
                return QueryResult(
                    answer=result.get("answer", "No answer generated"),
                    sources=result.get("sources", []),
                    confidence=result.get("confidence", 0.0),
                    latency_ms=latency,
                    error=result.get("error")
                )
                
            except Exception as e:
                self.logger.error("query_failed", error=str(e))
                span.set_attribute("error", str(e))
                
                return QueryResult(
                    answer="An error occurred while processing your question.",
                    sources=[],
                    confidence=0.0,
                    latency_ms=(time.time() - start) * 1000,
                    error=str(e)
                )
    
    async def aquery(
        self,
        question: str,
        thread_id: str = "default",
        user_id: Optional[str] = None
    ) -> QueryResult:
        """
        Process a RAG query asynchronously.
        """
        import time
        start = time.time()
        
        with tracer.start_as_current_span("orchestrator_aquery"):
            try:
                initial_state = create_initial_state(
                    question=question,
                    thread_id=thread_id,
                    user_id=user_id
                )
                
                config = {"configurable": {"thread_id": thread_id}}
                
                # Use async invoke
                result = await self.graph.ainvoke(initial_state, config)
                
                return QueryResult(
                    answer=result.get("answer", "No answer generated"),
                    sources=result.get("sources", []),
                    confidence=result.get("confidence", 0.0),
                    latency_ms=(time.time() - start) * 1000,
                    error=result.get("error")
                )
                
            except Exception as e:
                self.logger.error("async_query_failed", error=str(e))
                
                return QueryResult(
                    answer="An error occurred while processing your question.",
                    sources=[],
                    confidence=0.0,
                    latency_ms=(time.time() - start) * 1000,
                    error=str(e)
                )
    
    async def astream(
        self,
        question: str,
        thread_id: str = "default",
        user_id: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        """
        Stream response tokens for better perceived latency.
        
        Yields dicts with 'content' and 'done' keys.
        """
        initial_state = create_initial_state(
            question=question,
            thread_id=thread_id,
            user_id=user_id
        )
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # Stream through graph nodes
        async for event in self.graph.astream(initial_state, config):
            # Check for generated content
            if "generator" in event:
                answer = event["generator"].get("answer", "")
                if answer:
                    yield {"content": answer, "done": False}
            
            elif "fast_generator" in event:
                answer = event["fast_generator"].get("answer", "")
                if answer:
                    yield {"content": answer, "done": False}
        
        # Final done signal
        yield {"content": "", "done": True}
    
    def get_conversation_history(self, thread_id: str) -> list:
        """Get conversation history for a thread"""
        config = {"configurable": {"thread_id": thread_id}}
        state = self.graph.get_state(config)
        
        if state and state.values:
            return state.values.get("messages", [])
        return []
