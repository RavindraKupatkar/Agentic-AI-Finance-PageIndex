"""
PageIndex API Routes — Unified Endpoint File

ALL PageIndex endpoints live here in a single file:
    - POST /pageindex/query         — Ask a question
    - POST /pageindex/ingest        — Upload and index a PDF
    - GET  /pageindex/documents     — List indexed documents
    - GET  /pageindex/query/{id}    — Get query telemetry
    - GET  /pageindex/health        — Health check
    - GET  /pageindex/telemetry     — Recent query telemetry

This is the ONLY route file for the new PageIndex system.
Legacy routes (query.py, ingest.py, etc.) are kept for backward
compatibility but are not used by the new pipeline.

All endpoints use proper request/response Pydantic models.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ...agents.schemas.injected import create_deps
from ...agents.schemas.state import (
    create_initial_ingestion_state,
    create_initial_query_state,
)
from ...core.config import settings
from ...observability.logging import get_logger
from ...observability.telemetry import get_telemetry_service

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════
# Router
# ═══════════════════════════════════════════════════════════

router = APIRouter(prefix="/pageindex", tags=["PageIndex"])


# ═══════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELS
# ═══════════════════════════════════════════════════════════


class QueryRequest(BaseModel):
    """Request body for the /query endpoint."""

    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="The question to ask about the indexed documents.",
        examples=["What was the total revenue in Q4 2024?"],
    )
    thread_id: str = Field(
        default="default",
        description="Conversation thread ID for memory persistence.",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional user identifier for telemetry.",
    )


class SourceCitation(BaseModel):
    """A page-level source citation."""

    doc_id: str = Field(description="Document identifier")
    page_num: int = Field(description="1-indexed page number")
    filename: str = Field(default="", description="Original PDF filename")


class QueryResponse(BaseModel):
    """Response body for the /query endpoint."""

    answer: str = Field(description="Generated answer text")
    sources: list[SourceCitation] = Field(
        default_factory=list,
        description="Page-level source citations",
    )
    confidence: float = Field(
        ge=0, le=1, description="Overall confidence score"
    )
    query_type: str = Field(
        default="standard", description="Classified complexity"
    )
    query_id: str = Field(description="Telemetry tracking ID")
    latency_ms: float = Field(description="Total processing time in ms")
    warnings: list[str] = Field(
        default_factory=list,
        description="Any guardrail warnings",
    )


class IngestRequest(BaseModel):
    """Request body for the /ingest endpoint (JSON metadata)."""

    filename: Optional[str] = Field(
        default=None,
        description="Override filename for the uploaded PDF.",
    )


class IngestResponse(BaseModel):
    """Response body for the /ingest endpoint."""

    doc_id: str = Field(description="Generated document ID")
    filename: str = Field(description="PDF filename")
    title: str = Field(default="", description="Extracted document title")
    total_pages: int = Field(description="Total page count")
    tree_depth: int = Field(description="Depth of generated tree index")
    node_count: int = Field(description="Total nodes in tree index")
    stored: bool = Field(description="Whether the tree was saved")
    tree_path: str = Field(default="", description="Path to saved tree JSON")
    latency_ms: float = Field(description="Total processing time in ms")


class DocumentInfo(BaseModel):
    """Information about an indexed document."""

    doc_id: str
    filename: str
    title: str
    total_pages: int
    description: str = ""


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    telemetry_db: str = ""
    indexed_documents: int = 0
    groq_status: str = "unknown"


class TelemetryQueryLog(BaseModel):
    """A single query log entry for telemetry."""

    id: str
    thread_id: str
    question: str
    query_type: Optional[str] = None
    confidence: Optional[float] = None
    total_latency_ms: Optional[float] = None
    status: str
    created_at: str


class ErrorResponse(BaseModel):
    """Standardized error response."""

    detail: str
    query_id: Optional[str] = None


# ═══════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Ask a question about indexed documents",
    description="Processes a question through the PageIndex pipeline: "
    "input guardrail → router → document selection → tree search → "
    "page retrieval → critic → answer generation → output guardrail.",
)
async def query_documents(request: QueryRequest) -> QueryResponse:
    """
    🤖 QUERY — Full PageIndex query pipeline.

    Runs the complete LangGraph query graph:
    1. Input validation (PII, injection checks)
    2. Query complexity routing
    3. Document selection from indexed PDFs
    4. Tree-based reasoning search
    5. Page content extraction
    6. Quality evaluation (critic)
    7. Answer generation with citations
    8. Output validation
    """
    start_time = time.time()

    try:
        # Initialize telemetry and deps
        telemetry = await get_telemetry_service()
        query_id = await telemetry.start_query(
            question=request.question,
            thread_id=request.thread_id,
            user_id=request.user_id,
        )

        deps = await create_deps(query_id=query_id)

        # Create initial state
        initial_state = create_initial_query_state(
            question=request.question,
            thread_id=request.thread_id,
            user_id=request.user_id,
            query_id=query_id,
        )

        # Import and run graph
        from LangGraph_flow import get_query_graph

        graph = get_query_graph()
        config = {
            "configurable": {
                "thread_id": request.thread_id,
                "deps": deps,
            }
        }

        result = await graph.ainvoke(initial_state, config)

        latency_ms = (time.time() - start_time) * 1000

        # Log completion
        await telemetry.complete_query(
            query_id=query_id,
            answer=result.get("answer"),
            sources=result.get("sources"),
            confidence=result.get("confidence"),
            query_type=result.get("query_type"),
            total_latency_ms=latency_ms,
        )

        # Build response
        sources = [
            SourceCitation(
                doc_id=s.get("doc_id", ""),
                page_num=s.get("page_num", 0),
                filename=s.get("filename", ""),
            )
            for s in result.get("sources", [])
        ]

        return QueryResponse(
            answer=result.get("answer", "No answer generated"),
            sources=sources,
            confidence=result.get("confidence", 0.0),
            query_type=result.get("query_type", "standard"),
            query_id=query_id,
            latency_ms=round(latency_ms, 1),
            warnings=result.get("guardrail_warnings", []),
        )

    except Exception as exc:
        latency_ms = (time.time() - start_time) * 1000
        logger.error("query_endpoint.failed", error=str(exc))

        try:
            telemetry = await get_telemetry_service()
            await telemetry.log_error(
                error_type=type(exc).__name__,
                error_message=str(exc),
                node_name="api_query",
                exception=exc,
                recovery_action="return_500",
            )
        except Exception as log_exc:
            logger.warning("query_endpoint.telemetry_log_failed", error=str(log_exc))

        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Upload and index a PDF document",
    description="Ingests a PDF through the PageIndex pipeline: "
    "validation → metadata extraction → tree generation → storage.",
)
async def ingest_document(
    file: UploadFile = File(..., description="PDF file to ingest"),
) -> IngestResponse:
    """
    📄 INGEST — Full PageIndex document ingestion pipeline.

    Runs the complete LangGraph ingestion graph:
    1. File validation (type, size)
    2. PDF metadata extraction (pages, TOC, title)
    3. Tree index generation via LLM
    4. Tree storage to disk + metadata DB
    """
    start_time = time.time()

    try:
        # Validate upload
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400, detail="Only PDF files are accepted."
            )

        # Save uploaded file
        pdfs_dir = Path(settings.pdfs_dir)
        if not pdfs_dir.is_absolute():
            from ...core.config import _PROJECT_ROOT

            pdfs_dir = _PROJECT_ROOT / pdfs_dir
        pdfs_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = pdfs_dir / file.filename
        content = await file.read()

        # Size check
        if len(content) > settings.max_pdf_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {len(content) / (1024*1024):.1f}MB "
                f"(max {settings.max_pdf_size_mb}MB)",
            )

        pdf_path.write_bytes(content)

        # Initialize telemetry and deps
        telemetry = await get_telemetry_service()
        query_id = await telemetry.start_query(
            question=f"[INGEST] {file.filename}",
            thread_id="ingestion",
        )

        deps = await create_deps(query_id=query_id)

        # Create initial state
        initial_state = create_initial_ingestion_state(
            pdf_path=str(pdf_path),
            filename=file.filename,
            query_id=query_id,
        )

        # Run ingestion graph
        from LangGraph_flow import get_ingestion_graph

        graph = get_ingestion_graph()
        config = {"configurable": {"deps": deps}}

        result = await graph.ainvoke(initial_state, config)

        latency_ms = (time.time() - start_time) * 1000

        # Check for errors
        if result.get("error"):
            await telemetry.complete_query(
                query_id=query_id,
                error=result["error"],
                total_latency_ms=latency_ms,
            )
            raise HTTPException(status_code=422, detail=result["error"])

        await telemetry.complete_query(
            query_id=query_id,
            answer=f"Ingested {file.filename}: {result.get('node_count', 0)} nodes",
            total_latency_ms=latency_ms,
        )

        return IngestResponse(
            doc_id=result.get("doc_id", ""),
            filename=file.filename or "",
            title=result.get("title", ""),
            total_pages=result.get("total_pages", 0),
            tree_depth=result.get("tree_depth", 0),
            node_count=result.get("node_count", 0),
            stored=result.get("stored", False),
            tree_path=result.get("tree_path", ""),
            latency_ms=round(latency_ms, 1),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("ingest_endpoint.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/documents",
    response_model=list[DocumentInfo],
    summary="List all indexed documents",
)
async def list_documents() -> list[DocumentInfo]:
    """📚 LIST — Get all indexed documents and their metadata."""
    try:
        deps = await create_deps()
        docs = deps.tree_store.list_documents()

        return [
            DocumentInfo(
                doc_id=doc.doc_id,
                filename=doc.filename,
                title=doc.title,
                total_pages=doc.total_pages,
                description="",
            )
            for doc in docs
        ]
    except Exception as exc:
        logger.error("list_documents.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/query/{query_id}",
    summary="Get query telemetry by ID",
)
async def get_query_telemetry(query_id: str) -> dict:
    """📊 TELEMETRY — Get full telemetry for a specific query."""
    try:
        telemetry = await get_telemetry_service()

        query_log = await telemetry.get_query_log(query_id)
        if not query_log:
            raise HTTPException(status_code=404, detail=f"Query {query_id} not found")

        nodes = await telemetry.get_node_executions(query_id)
        llm_calls = await telemetry.get_llm_calls(query_id)
        errors = await telemetry.get_errors(query_id=query_id)

        return {
            "query": query_log,
            "node_executions": nodes,
            "llm_calls": llm_calls,
            "errors": errors,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/telemetry",
    response_model=list[TelemetryQueryLog],
    summary="Get recent query telemetry",
)
async def get_recent_telemetry(limit: int = 20) -> list[TelemetryQueryLog]:
    """📊 TELEMETRY — Get recent queries from telemetry DB."""
    try:
        telemetry = await get_telemetry_service()
        queries = await telemetry.get_recent_queries(limit=limit)

        return [
            TelemetryQueryLog(
                id=q["id"],
                thread_id=q["thread_id"],
                question=q["question"],
                query_type=q.get("query_type"),
                confidence=q.get("confidence"),
                total_latency_ms=q.get("total_latency_ms"),
                status=q["status"],
                created_at=q["created_at"],
            )
            for q in queries
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="PageIndex system health check",
)
async def health_check() -> HealthResponse:
    """🏥 HEALTH — Check all PageIndex system components."""
    try:
        # Check telemetry
        telemetry = await get_telemetry_service()
        telemetry_status = "ok" if telemetry._initialized else "not_initialized"

        # Check indexed documents
        try:
            deps = await create_deps()
            docs = deps.tree_store.list_documents()
            doc_count = len(docs)
        except Exception:
            doc_count = 0

        # Check Groq API
        groq_status = "unknown"
        try:
            from ...llm.groq_client import GroqClient

            client = GroqClient()
            groq_status = "ok" if client.health_check() else "error"
        except Exception:
            groq_status = "error"

        return HealthResponse(
            status="ok",
            telemetry_db=telemetry_status,
            indexed_documents=doc_count,
            groq_status=groq_status,
        )
    except Exception as exc:
        return HealthResponse(
            status="error",
            telemetry_db=str(exc),
        )


@router.get(
    "/page/{doc_id}/{page_num}",
    summary="Get page content for citation verification",
)
async def get_page_content(doc_id: str, page_num: int) -> dict:
    """📄 PAGE — Extract text content from a specific PDF page for citation verification."""
    try:
        deps = await create_deps()

        # Find the document filename
        docs = deps.tree_store.list_documents()
        target_doc = None
        for doc in docs:
            if doc.doc_id == doc_id:
                target_doc = doc
                break

        if not target_doc:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

        # Resolve PDF path
        pdf_path = settings.pdfs_dir_absolute / target_doc.filename
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail=f"PDF file not found: {target_doc.filename}")

        # Extract page content
        result = deps.page_extractor.extract_pages(
            pdf_path=str(pdf_path),
            page_numbers=[page_num],
            doc_id=doc_id,
        )

        page_text = ""
        if result.pages:
            page_text = result.pages[0].text

        return {
            "doc_id": doc_id,
            "page_num": page_num,
            "filename": target_doc.filename,
            "content": page_text,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_page_content.failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
