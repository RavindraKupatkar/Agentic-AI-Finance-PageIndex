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
        # Load all document metadata from TreeStore
        all_docs = deps.tree_store.list_documents()

        if not all_docs:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning("doc_selector.no_documents")
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
                "error": "No documents indexed. Please ingest documents first.",
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
        tree_structures: dict = {}
        for doc_id in selected_ids:
            tree_data = deps.tree_store.load_tree(doc_id)
            if tree_data:
                # Store as dict for LangGraph state serialization
                tree_structures[doc_id] = (
                    tree_data.to_dict()
                    if hasattr(tree_data, "to_dict")
                    else tree_data
                )

        duration_ms = (time.time() - start_time) * 1000

        await deps.telemetry.log_node_end(
            node_execution_id=node_exec_id,
            query_id=state.get("query_id", ""),
            node_name="doc_selector",
            output_summary={
                "available": len(available_docs),
                "selected": len(selected_ids),
                "selected_ids": selected_ids,
            },
            duration_ms=duration_ms,
        )

        logger.info(
            "doc_selector.complete",
            available=len(available_docs),
            selected=len(selected_ids),
            selected_ids=selected_ids,
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
