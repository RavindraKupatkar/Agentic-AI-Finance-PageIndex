"""
Page Retrieve Node — Extract Text from Identified PDF Pages (NEW)

Takes the page numbers from tree_search and extracts the actual text
content from the source PDFs using PageExtractor.

This is a NEW node in the PageIndex pipeline.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import asyncio
import time
from typing import Any

from ..schemas.state import PageIndexQueryState
from ..schemas.injected import get_deps
from ...observability.logging import get_logger

logger = get_logger(__name__)

async def retrieve_pages(
    state: PageIndexQueryState, config: RunnableConfig
) -> dict[str, Any]:
    """
    📑 PAGE RETRIEVE — Extract text from identified PDF pages.

    Takes the page numbers from tree_search and extracts the actual
    text content from the source PDFs using PageExtractor.

    Args:
        state: Current state with relevant_pages, tree_structures.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with page_contents and merged context string.
    """
    start_time = time.time()
    deps = get_deps(config)
    relevant_pages = state.get("relevant_pages", {})
    tree_structures = state.get("tree_structures", {})

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="page_retrieve",
        input_summary={
            "doc_count": len(relevant_pages),
            "total_pages": sum(len(p) for p in relevant_pages.values()),
        },
    )

    try:
        page_contents: list[dict] = []

        for doc_id, page_numbers in relevant_pages.items():
            if not page_numbers:
                continue

            # Resolve full PDF path via TreeStore metadata
            doc_meta = deps.tree_store.get_metadata(doc_id)
            if doc_meta and doc_meta.pdf_path:
                pdf_path = doc_meta.pdf_path
                filename = doc_meta.filename
            else:
                # Fallback: try to get filename from tree structure
                tree_data = tree_structures.get(doc_id, {})
                if isinstance(tree_data, dict):
                    filename = tree_data.get("filename", "")
                else:
                    filename = getattr(tree_data, "filename", "")
                # Try data/pdfs/ directory
                from pathlib import Path
                pdf_path = str(Path("data/pdfs") / filename) if filename else ""

            if not pdf_path:
                logger.warning("page_retrieve.no_pdf_path", doc_id=doc_id)
                continue

            # Extract pages using PageExtractor (CPU-bound → thread pool)
            try:
                result = await asyncio.to_thread(
                    deps.page_extractor.extract_pages,
                    pdf_path,
                    page_numbers,
                    doc_id,
                )

                # ExtractionResult.pages is a list of PageContent objects
                for page in result.pages:
                    page_contents.append({
                        "doc_id": doc_id,
                        "page_num": page.page_number,
                        "text": page.text,
                        "filename": filename,
                    })
            except Exception as page_exc:
                logger.warning(
                    "page_retrieve.extraction_failed",
                    doc_id=doc_id,
                    pdf_path=pdf_path,
                    error=str(page_exc),
                )
                continue

        # Build merged context string from all pages
        context_parts: list[str] = []
        for pc in sorted(page_contents, key=lambda x: (x["doc_id"], x["page_num"])):
            header = f"[{pc['filename']}, Page {pc['page_num']}]"
            context_parts.append(f"{header}\n{pc['text']}")

        context = "\n\n---\n\n".join(context_parts)

        # Truncate context if too long (LLM context window)
        max_context_chars = 8000
        if len(context) > max_context_chars:
            context = context[:max_context_chars] + "\n\n[Context truncated...]"

        duration_ms = (time.time() - start_time) * 1000

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="page_retrieve",
            output_summary={
                "pages_extracted": len(page_contents),
                "context_length": len(context),
            },
            duration_ms=duration_ms,
        )

        logger.info(
            "page_retrieve.complete",
            pages_extracted=len(page_contents),
            context_chars=len(context),
        )

        return {
            "page_contents": page_contents,
            "context": context,
        }

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("page_retrieve.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="page_retrieve",
            duration_ms=duration_ms,
            error=str(exc),
        )
        return {
            "page_contents": [],
            "context": "",
            "error": f"Page retrieval failed: {str(exc)}",
        }
