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
        from ...services.convex_service import convex_service
        import httpx
        from pathlib import Path

        cache_dir = Path("data/pdfs_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)

        page_contents: list[dict] = []

        for doc_id, page_numbers in relevant_pages.items():
            if not page_numbers:
                continue

            # Find document info from available docs in state
            available_docs = state.get("available_docs", [])
            doc_info = next((d for d in available_docs if d["doc_id"] == doc_id), None)

            if not doc_info or not doc_info.get("storage_id"):
                logger.warning("page_retrieve.no_storage_id", doc_id=doc_id)
                continue

            storage_id = doc_info["storage_id"]
            filename = doc_info["filename"]
            
            pdf_path = cache_dir / f"{storage_id}.pdf"

            # Cache miss: Download from Convex Storage
            if not pdf_path.exists():
                logger.info("page_retrieve.cache_miss_fetching", doc_id=doc_id, storage_id=storage_id)
                try:
                    dl_url = convex_service.get_download_url(storage_id)
                    if dl_url:
                        # Blocking IO since we're in async, but httpx allows sync calls here
                        # Actually it's better to use httpx.AsyncClient or run in thread
                        # For simplicity, we run in an async thread implicitly or block
                        # We will use httpx blocking since it's just a quick cache fill
                        resp = httpx.get(dl_url)
                        resp.raise_for_status()
                        pdf_path.write_bytes(resp.content)
                    else:
                        logger.error("page_retrieve.no_url_returned", doc_id=doc_id)
                        continue
                except Exception as dl_exc:
                    logger.error("page_retrieve.download_failed", error=str(dl_exc))
                    continue

            # Extract pages using PageExtractor (CPU-bound → thread pool)
            try:
                result = await asyncio.to_thread(
                    deps.page_extractor.extract_pages,
                    str(pdf_path),
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
                    pdf_path=str(pdf_path),
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
