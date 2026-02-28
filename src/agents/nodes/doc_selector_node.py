"""
Doc Selector Node — Document Selection from Metadata (NEW)

Selects which indexed documents to search based on question relevance.
Loads metadata from TreeStore and uses LLM to pick the most relevant
documents before tree search begins.

This is a NEW node unique to the PageIndex pipeline.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import json
import time
from typing import Any

from ..schemas.state import PageIndexQueryState
from ..schemas.injected import get_deps
from ...observability.logging import get_logger

logger = get_logger(__name__)

_DOC_SELECTOR_PROMPT = """You are selecting which documents to search to answer a question.

Question: {question}

Available documents:
{doc_list}

Select the documents most likely to contain the answer. Output a JSON array of document IDs:
["doc_id_1", "doc_id_2"]

Rules:
1. Select at most {max_docs} documents
2. If unsure, select all documents
3. Output ONLY valid JSON, no explanation"""

async def select_documents(
    state: PageIndexQueryState, config: RunnableConfig
) -> dict[str, Any]:
    """
    📚 DOC SELECTOR — Pick which documents to search from metadata.

    Reads metadata of all indexed documents from TreeStore and asks
    LLM which documents likely contain the answer.

    Args:
        state: Current state with question field.
        config: RunnableConfig with injected PageIndexDeps.

    Returns:
        Dict with available_docs, selected_doc_ids, and tree_structures.
    """
    start_time = time.time()
    deps = get_deps(config)
    question = state["question"]

    node_exec_id = await deps.telemetry.log_node_start(
        query_id=state.get("query_id", ""),
        node_name="doc_selector",
        input_summary={"question_length": len(question)},
    )

    try:
        # Load all document metadata from TreeStore (validate=True
        # automatically purges entries whose JSON files are missing)
        all_docs = deps.tree_store.list_documents(validate=True)

        # ── Conversation-scoped filtering ──────────────────────────
        # If the query came from a conversation with attached documents,
        # ONLY search those specific documents (not the entire library).
        scoped_doc_ids = state.get("scoped_doc_ids")
        if scoped_doc_ids:
            scoped_set = set(scoped_doc_ids)
            all_docs = [d for d in all_docs if d.doc_id in scoped_set]
            logger.info(
                "doc_selector.scoped_filter_applied",
                scoped_doc_ids=scoped_doc_ids,
                docs_after_filter=len(all_docs),
            )

        if not all_docs:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = (
                "No matching documents found for this conversation."
                if scoped_doc_ids
                else "No documents indexed. Please ingest documents first."
            )
            logger.warning("doc_selector.no_documents", scoped=bool(scoped_doc_ids))
            await deps.telemetry.log_node_end(
                node_execution_id=node_exec_id,
                query_id=state.get("query_id", ""),
                node_name="doc_selector",
                output_summary={"selected": 0, "available": 0},
                duration_ms=duration_ms,
            )
            return {
                "available_docs": [],
                "selected_doc_ids": [],
                "tree_structures": {},
                "error": error_msg,
            }

        available_docs = [
            {
                "doc_id": doc.doc_id,
                "filename": doc.filename,
                "title": doc.title,
                "description": "",
                "total_pages": doc.total_pages,
            }
            for doc in all_docs
        ]

        # If only 1 document, select it directly (no LLM needed)
        if len(available_docs) == 1:
            selected_ids = [available_docs[0]["doc_id"]]
        else:
            # Use LLM to select relevant documents
            doc_list_parts = []
            for i, doc in enumerate(available_docs):
                desc = doc.get("description", "") or doc.get("title", "")
                doc_list_parts.append(
                    f'{i + 1}. [{doc["doc_id"]}] "{doc["filename"]}" '
                    f'({doc["total_pages"]} pages)\n   Description: {desc}'
                )

            prompt = _DOC_SELECTOR_PROMPT.format(
                question=question,
                doc_list="\n\n".join(doc_list_parts),
                max_docs=min(5, len(available_docs)),
            )

            llm_start = time.time()
            response = await deps.llm.agenerate(
                prompt=prompt,
                model="llama-3.1-8b-instant",
                max_tokens=256,
                temperature=0.0,
            )
            llm_latency = (time.time() - llm_start) * 1000

            await deps.telemetry.log_llm_call(
                query_id=state.get("query_id", ""),
                node_name="doc_selector",
                model="llama-3.1-8b-instant",
                latency_ms=round(llm_latency, 1),
                temperature=0.0,
            )

            selected_ids = _parse_selected_ids(response, available_docs)

        # Load tree structures for selected documents
        # Gracefully skip documents whose trees can't be loaded
        tree_structures: dict = {}
        failed_ids: list[str] = []
        for doc_id in selected_ids:
            try:
                tree_data = deps.tree_store.load_tree(doc_id)
                if tree_data:
                    tree_structures[doc_id] = (
                        tree_data.to_dict()
                        if hasattr(tree_data, "to_dict")
                        else tree_data
                    )
                else:
                    logger.warning(
                        "doc_selector.tree_load_skipped",
                        doc_id=doc_id,
                        reason="load_tree returned None (stale entry cleaned)",
                    )
                    failed_ids.append(doc_id)
            except Exception as load_exc:
                logger.warning(
                    "doc_selector.tree_load_failed",
                    doc_id=doc_id,
                    error=str(load_exc),
                )
                failed_ids.append(doc_id)

        # Remove failed doc_ids from the selected list
        if failed_ids:
            selected_ids = [d for d in selected_ids if d not in failed_ids]

        duration_ms = (time.time() - start_time) * 1000

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="doc_selector",
            output_summary={
                "available": len(available_docs),
                "selected": len(selected_ids),
                "selected_ids": selected_ids,
                "skipped": len(failed_ids),
            },
            duration_ms=duration_ms,
        )

        logger.info(
            "doc_selector.complete",
            available=len(available_docs),
            selected=len(selected_ids),
            selected_ids=selected_ids,
            skipped=failed_ids if failed_ids else None,
        )

        return {
            "available_docs": available_docs,
            "selected_doc_ids": selected_ids,
            "tree_structures": tree_structures,
        }

    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error("doc_selector.failed", error=str(exc))
        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="doc_selector",
            duration_ms=duration_ms,
            error=str(exc),
        )
        await deps.telemetry.log_error(
            error_type=type(exc).__name__,
            error_message=str(exc),
            query_id=state.get("query_id", ""),
            node_name="doc_selector",
            exception=exc,
            recovery_action="abort",
        )
        return {
            "available_docs": [],
            "selected_doc_ids": [],
            "tree_structures": {},
            "error": f"Document selection failed: {str(exc)}",
        }

def _parse_selected_ids(response: str, available_docs: list[dict]) -> list[str]:
    """Parse LLM response to extract selected document IDs."""
    valid_ids = {doc["doc_id"] for doc in available_docs}

    try:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        start = cleaned.find("[")
        end = cleaned.rfind("]") + 1
        if start >= 0 and end > start:
            cleaned = cleaned[start:end]

        ids = json.loads(cleaned)
        if isinstance(ids, list):
            return [i for i in ids if i in valid_ids]
    except (json.JSONDecodeError, ValueError):
        logger.warning("doc_selector.parse_failed", response_preview=response[:100])

    # Fallback: select all documents
    return [doc["doc_id"] for doc in available_docs]
