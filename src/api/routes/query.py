"""
Query Routes - Handle RAG queries
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import time

from ..schemas.request import QueryRequest
from ..schemas.response import QueryResponse, StreamChunk
from ...agents.orchestrator import AgentOrchestrator
from ...observability.metrics import QUERY_LATENCY, QUERY_COUNT

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Process a RAG query and return response
    """
    start_time = time.time()
    
    try:
        orchestrator = AgentOrchestrator()
        result = await orchestrator.aquery(
            question=request.question,
            thread_id=request.thread_id,
            user_id=request.user_id
        )
        
        latency_ms = (time.time() - start_time) * 1000
        QUERY_LATENCY.observe(latency_ms / 1000)
        QUERY_COUNT.labels(status="success").inc()
        
        return QueryResponse(
            answer=result.answer,
            sources=result.sources,
            confidence=result.confidence,
            latency_ms=latency_ms
        )
        
    except Exception as e:
        QUERY_COUNT.labels(status="error").inc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
async def query_rag_stream(request: QueryRequest):
    """
    Stream RAG response for better perceived latency
    """
    orchestrator = AgentOrchestrator()
    
    async def generate():
        async for chunk in orchestrator.astream(
            question=request.question,
            thread_id=request.thread_id
        ):
            yield f"data: {chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
