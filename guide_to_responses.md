# PageIndex RAG: Understanding Responses & Telemetry Guide

This guide explains how to interpret the responses from the PageIndex system, analyze the reasoning process, and use telemetry to verify answers.

## 1. Validating Ingestion Responses

When you upload a PDF via `POST /ingest`, the system extracts metadata, generates a hierarchical tree index, and stores it.

**Example Response:**
```json
{
  "doc_id": "doc_12345",
  "filename": "Q3_Report.pdf",
  "title": "Quarterly Report Q3 2024",
  "total_pages": 45,
  "tree_depth": 3,
  "node_count": 128,
  "stored": true,
  "tree_path": "data/trees/doc_12345.json",
  "latency_ms": 4500.2
}
```

**Key Fields to Check:**
- **`node_count`**: Should reflect complexity. A 45-page report might have ~100-150 nodes. Very low counts indicate extraction failure.
- **`tree_depth`**: Indicates hierarchy depth. Depth 1 = flat list, Depth 3+ = rich structure (Sections -> Subsections -> Content). PageIndex relies on this structure for effective *reasoning*.
- **`stored`**: confirm `true`. If `false`, check `ingestion_error` in logs.

---

## 2. Analyzing Query Responses (`POST /query`)

The query response tells you *what* the answer is, *where* it came from, and *how confident* the system is.

**Example Response:**
```json
{
  "answer": "The total revenue for Q3 2024 was $12.5B, driven by a 15% increase in cloud services.",
  "sources": [
    {
      "doc_id": "doc_12345",
      "page_num": 12,
      "filename": "Q3_Report.pdf"
    },
    {
      "doc_id": "doc_12345",
      "page_num": 14,
      "filename": "Q3_Report.pdf"
    }
  ],
  "confidence": 0.9,
  "query_type": "standard",
  "query_id": "query_98765",
  "latency_ms": 2100.5,
  "warnings": []
}
```

### Understanding the Fields

| Field | Meaning | Analysis Tips |
| :--- | :--- | :--- |
| **`answer`** | The generated response. | Check if it directly answers the question. "I cannot verify..." usually means low confidence retrieval. |
| **`sources`** | Page-level citations. | **Critical:** Verify these pages contain the supporting info. PageIndex retrieves *exact pages*, not chunk snippets. |
| **`confidence`** | Score (0.0 - 1.0). | **> 0.8**: High confidence. **< 0.5**: Likely hallucination or missing data. **0.0**: Retrieval failure or guardrail block. |
| **`query_type`** | Routing logic used. | **`simple`**: Direct keyword lookup (Fast Path). **`standard`**: Tree Search + Reasoning. **`complex`**: Planning + Multi-step query breakdown. |
| **`warnings`** | Guardrail alerts. | Look for `"Potential prompt injection"` or `"Answer generated without source citations"`. |

---

## 3. Deep Dive with Telemetry (`GET /query/{id}`)

If an answer looks suspicious or you want to verify the reasoning, use the `query_id` to fetch the full trace.

**Example Telemetry Structure:**
```json
{
  "query": { ... },
  "node_executions": [
    { "node_name": "router", "output_summary": { "query_type": "standard" } },
    { "node_name": "doc_selector", "output_summary": { "selected_doc_ids": ["doc_12345"] } },
    { "node_name": "tree_search", "output_summary": { "reasoning_trace": [ ... ] } }
  ],
  "llm_calls": [ ... ],
  "errors": []
}
```

### Inspecting the Reasoning Trace (`tree_search` node)

This is the most powerful feature. It shows the LLM's thought process as it navigates the document tree.

**Look for `reasoning_trace` in `node_executions`:**
- **Step 1 (Root)**: "I see sections: Financials, Operations, Risks. The question asks about revenue, so I will explore 'Financials'."
- **Step 2 (Branch)**: "Inside Financials, I see: Q1, Q2, Q3 results. I will drill into 'Q3 Results'."
- **Step 3 (Leaf)**: "Page 12 contains the Consolidated Statement of Income. This is relevant."

**Troubleshooting using Trace:**
- **Stuck at Root?** The tree summary might be vague. Improving extraction/summarization quality fixes this.
- **Wrong Branch?** The reasoning model (LLM) might have misinterpreted the question. Check `router` classification.

---

## 4. Common Response Scenarios

### Scenario A: "I cannot answer this question based on the provided documents."
- **Confidence**: Low (< 0.5).
- **Sources**: Document list empty or irrelevant pages.
- **Cause**: The `TreeSearcher` failed to find relevant pages, so the `PageRetrieve` node returned empty context.
- **Fix**: Check `tree_search` reasoning in telemetry. Did it miss a branch? Or is the info truly missing?

### Scenario B: Guardrail Block (Prompt Injection)
- **Answer**: "Your query was flagged for potential prompt injection."
- **Confidence**: 0.0.
- **Warnings**: `["Potential prompt injection detected"]`.
- **Cause**: Input matched injection patterns (e.g., "Ignore previous instructions").

### Scenario C: Fast Path (`simple` query) result is wrong.
- **Query Type**: `simple`.
- **Cause**: The Router classified a nuanced question as "simple".
- **Fix**: Check `router` reasoning. Sometimes keyword match isn't enough. You might force "standard" routing for higher accuracy or adjust router prompts.

---

## 5. Verifying Accuracy Manually

1. **Ask a verifiable question**: "What is the net income on page 15?"
2. **Check the `sources` array**: Does it list `page_num: 15`?
3. **Verify content**: Open the PDF to page 15.
4. **If using `complex` mode**: Check `planner` node output in telemetry. Did it break the question down correctly (e.g., "First find revenue, then find expenses, then calculate net income")?
