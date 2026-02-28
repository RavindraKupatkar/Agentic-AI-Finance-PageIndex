"""
Ingestion Nodes — Document Ingestion Pipeline (PageIndex)

LangGraph nodes for the document ingestion pipeline:
    - validate_document:    Check file exists, is PDF, within limits
    - extract_pdf_metadata: Extract title, page count, TOC
    - generate_tree_index:  Call TreeGenerator to build tree
    - store_tree:           Save tree to TreeStore
    - ingestion_error:      Handle errors gracefully
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import asyncio
import time
from pathlib import Path
from typing import Any

from ..schemas.state import PageIndexIngestionState
from ..schemas.injected import get_deps
from ...core.config import settings
from ...observability.logging import get_logger

logger = get_logger(__name__)

async def validate_document(
    state: PageIndexIngestionState, config: RunnableConfig
) -> dict[str, Any]:
    """
    📄 VALIDATE DOCUMENT — Check file exists, is PDF, within size limits.

    Args:
        state: Current ingestion state with pdf_path.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with is_valid and validation_error.
    """
    deps = get_deps(config)
    pdf_path = Path(state["pdf_path"]).resolve()

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="validate_document",
        input_summary={"pdf_path": str(pdf_path)},
    )

    start_time = time.time()

    try:
        # Check existence
        if not pdf_path.exists():
            return _validation_fail(
                f"File not found: {pdf_path}",
                deps, node_exec_id, state, start_time,
            )

        # Check extension
        if pdf_path.suffix.lower() != ".pdf":
            return _validation_fail(
                f"Not a PDF file: {pdf_path.suffix}",
                deps, node_exec_id, state, start_time,
            )

        # Check size
        file_size = pdf_path.stat().st_size
        max_size = settings.max_pdf_size_bytes
        if file_size > max_size:
            return _validation_fail(
                f"File too large: {file_size / (1024*1024):.1f}MB (max {settings.max_pdf_size_mb}MB)",
                deps, node_exec_id, state, start_time,
            )

        if file_size == 0:
            return _validation_fail(
                "File is empty",
                deps, node_exec_id, state, start_time,
            )

        duration_ms = (time.time() - start_time) * 1000
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="validate_document",
            output_summary={"valid": True, "size_mb": round(file_size / (1024*1024), 2)},
            duration_ms=duration_ms,
        )

        return {"is_valid": True, "validation_error": None}

    except Exception as exc:
        return _validation_fail(
            str(exc), deps, node_exec_id, state, start_time,
        )

async def _validation_fail(
    error: str, deps, node_exec_id: int, state: dict, start_time: float
) -> dict:
    """Helper to record validation failure in telemetry."""
    duration_ms = (time.time() - start_time) * 1000
    await deps.telemetry.log_node_end(
        node_execution_id=node_exec_id,
        query_id=state.get("query_id", ""),
        node_name="validate_document",
        output_summary={"valid": False, "error": error},
        duration_ms=duration_ms,
        error=error,
    )
    return {"is_valid": False, "validation_error": error}

async def extract_pdf_metadata(
    state: PageIndexIngestionState, config: RunnableConfig
) -> dict[str, Any]:
    """
    📋 EXTRACT PDF METADATA — PyMuPDF: page count, TOC, title, texts.

    Extracts structural information from the PDF file that will be
    used by the tree generator.

    Args:
        state: Current ingestion state with pdf_path.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with total_pages, title, existing_toc, page_texts.
    """
    start_time = time.time()
    deps = get_deps(config)
    pdf_path = state["pdf_path"]

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="extract_pdf_metadata",
        input_summary={"pdf_path": pdf_path},
    )

    try:
        # CPU-bound extraction in thread pool — use correct method name
        metadata = await asyncio.to_thread(
            deps.page_extractor.get_document_metadata, pdf_path
        )

        total_pages = metadata.page_count

        # Check page limit
        if total_pages > settings.max_pdf_pages:
            error_msg = f"Too many pages: {total_pages} (max {settings.max_pdf_pages})"
            duration_ms = (time.time() - start_time) * 1000
            await deps.telemetry.log_node_end(
                node_execution_id=node_exec_id,
                query_id=state.get("query_id", ""),
                node_name="extract_pdf_metadata",
                duration_ms=duration_ms,
                error=error_msg,
            )
            return {
                "is_valid": False,
                "validation_error": error_msg,
                "total_pages": total_pages,
                "title": metadata.title,
                "existing_toc": metadata.toc,
                "page_texts": [],
            }

        # Extract all page texts using extract_page_range
        extraction = await asyncio.to_thread(
            deps.page_extractor.extract_page_range,
            pdf_path,
            1,              # start_page (1-indexed)
            total_pages,    # end_page (inclusive)
        )
        page_texts = [p.text for p in extraction.pages]

        duration_ms = (time.time() - start_time) * 1000

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="extract_pdf_metadata",
            output_summary={
                "total_pages": total_pages,
                "title": metadata.title[:50],
                "has_toc": metadata.has_toc,
            },
            duration_ms=duration_ms,
        )

        return {
            "total_pages": total_pages,
            "title": metadata.title,
            "existing_toc": metadata.toc,
            "page_texts": page_texts,
        }

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("extract_pdf_metadata.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="extract_pdf_metadata",
            duration_ms=duration_ms,
            error=str(exc),
        )
        return {
            "is_valid": False,
            "validation_error": f"Metadata extraction failed: {str(exc)}",
            "error": str(exc),
        }

async def generate_tree_index(
    state: PageIndexIngestionState, config: RunnableConfig
) -> dict[str, Any]:
    """
    🌲 GENERATE TREE INDEX — LLM builds hierarchical tree from document.

    ⏱️ Slowest step (~30-60s per document)

    Args:
        state: Current state with pdf_path and page_texts.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with doc_id, tree_structure, tree_depth, node_count.
    """
    start_time = time.time()
    deps = get_deps(config)
    pdf_path = state["pdf_path"]

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="generate_tree_index",
        input_summary={
            "pdf_path": pdf_path,
            "total_pages": state.get("total_pages", 0),
        },
    )

    try:
        from ...pageindex.tree_generator import TreeGenerator

        generator = TreeGenerator(
            llm=deps.llm,
            telemetry=deps.telemetry,
            query_id=state.get("query_id"),
        )

        tree = await generator.generate_tree(pdf_path)

        # Ensure the tree uses the Document ID from Convex
        tree.doc_id = state.get("doc_id", tree.doc_id)
        
        duration_ms = (time.time() - start_time) * 1000

        tree_dict = tree.to_dict()

        # Inline helpers — TreeGenerator doesn't expose these
        def _depth(nodes, level=1):
            if not nodes:
                return 0
            return max(
                level if not n.children else _depth(n.children, level + 1)
                for n in nodes
            )

        def _count(nodes):
            return sum(1 + _count(n.children) for n in nodes)

        tree_depth = _depth(tree.root_nodes)
        node_count = _count(tree.root_nodes)

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="generate_tree_index",
            output_summary={
                "doc_id": tree.doc_id,
                "tree_depth": tree_depth,
                "node_count": node_count,
            },
            duration_ms=duration_ms,
        )

        logger.info(
            "generate_tree_index.complete",
            doc_id=tree.doc_id,
            depth=tree_depth,
            nodes=node_count,
            elapsed_ms=round(duration_ms, 1),
        )

        return {
            "doc_id": tree.doc_id,
            "tree_structure": tree_dict,
            "tree_depth": tree_depth,
            "node_count": node_count,
        }

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("generate_tree_index.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="generate_tree_index",
            duration_ms=duration_ms,
            error=str(exc),
        )
        await deps.telemetry.log_error(
            error_type=type(exc).__name__,
            error_message=str(exc),
            query_id=state.get("query_id", ""),
            node_name="generate_tree_index",
            exception=exc,
            recovery_action="abort",
        )
        return {"error": f"Tree generation failed: {str(exc)}"}

async def store_tree(
    state: PageIndexIngestionState, config: RunnableConfig
) -> dict[str, Any]:
    """
    💾 STORE TREE — Save tree JSON to Convex and update document metadata.

    Args:
        state: Current state with doc_id and tree_structure.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with tree_path and stored flag.
    """
    start_time = time.time()
    deps = get_deps(config)
    doc_id = state.get("doc_id", "")
    tree_structure = state.get("tree_structure")

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="store_tree",
        input_summary={"doc_id": doc_id},
    )

    try:
        from ...services.convex_service import convex_service

        if not tree_structure:
            raise ValueError("No tree structure to store")

        # Save to Convex
        convex_service.save_tree(doc_id, tree_structure)

        nodes = state.get("node_count", 0)
        depth = state.get("tree_depth", 0)
        pages = state.get("total_pages", 0)

        # Update document status to "ready"
        convex_service.update_document_status(
            document_id=doc_id,
            status="ready",
            totalPages=pages,
            treeDepth=depth,
            nodeCount=nodes
        )

        # Cleanup temporary local PDF file used by PyMuPDF
        pdf_path = state.get("pdf_path")
        if pdf_path:
            Path(pdf_path).unlink(missing_ok=True)

        duration_ms = (time.time() - start_time) * 1000

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="store_tree",
            output_summary={"stored": True},
            duration_ms=duration_ms,
        )

        logger.info("store_tree.complete", doc_id=doc_id)

        return {"tree_path": "convex://trees", "stored": True}

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("store_tree.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="store_tree",
            duration_ms=duration_ms,
            error=str(exc),
        )
        return {"tree_path": "", "stored": False, "error": str(exc)}

async def ingestion_error(
    state: PageIndexIngestionState, config: RunnableConfig
) -> dict[str, Any]:
    """
    ❌ INGESTION ERROR — Handle validation/processing errors.

    Args:
        state: Current state with validation_error or error.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with error message.
    """
    deps = get_deps(config)
    error_msg = state.get("validation_error") or state.get("error") or "Unknown ingestion error"

    await deps.telemetry.log_error(
        error_type="IngestionError",
        error_message=error_msg,
        query_id=state.get("query_id", ""),
        node_name="ingestion_error",
        recovery_action="abort",
    )

    logger.error("ingestion_error", error=error_msg)

    return {"error": error_msg, "stored": False}
