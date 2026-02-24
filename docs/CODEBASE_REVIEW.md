# Codebase Review -- Things to Keep in Mind Before Moving Forward

This document is a thorough review of the **Agentic-AI-Finance-PageIndex** repository. Your project is built around the **PageIndex approach from Vectify**, which is fundamentally different from traditional RAG. I will explain every finding in detail, call out where the current code still follows a traditional RAG pattern (which contradicts your intended architecture), and give you a clear fix list.

---

## Understanding Your Intended Architecture (PageIndex)

Based on the **PageIndex Finance RAG System Architecture** diagram, your system is supposed to work like this:

**What PageIndex IS:**
- Documents are indexed as a **hierarchical tree** (like a table of contents / tree index), not as flat vector embeddings
- At query time, an **LLM reasons its way through the tree** to find the right pages -- it navigates the hierarchy using intelligence, not similarity search
- Retrieval happens at the **page level** -- whole pages are returned, not small chunks
- There is **no vector database** and **no chunking** (both are explicitly crossed out with red X's in your architecture diagram)
- The ingestion pipeline builds a **Tree Index** (hierarchical TOC) and stores **Page Content**, not embeddings

**What PageIndex is NOT:**
- It is NOT "embed chunks into vectors, then do similarity search" (that is traditional RAG)
- It is NOT "BM25 + vector search + reranking" (that is hybrid RAG)
- It does NOT need a vector database like Qdrant, FAISS, or ChromaDB

**Your intended flow (from the diagram):**
1. User sends request to FastAPI
2. Input Guardrails validate the request
3. LangGraph Orchestrator receives the sanitized query
4. Router Node classifies query complexity
5. **Tree Search Agent Node** (the KEY innovation) navigates the hierarchical tree index using LLM reasoning
6. Critic Node evaluates retrieval quality (self-correction loop)
7. Generator Node produces the answer with citations
8. Output Guardrails check for hallucination, finance compliance, disclaimers
9. Response returned to user

---

## THE BIG PROBLEM: Your Code Implements Traditional RAG, Not PageIndex

This is the most important finding. The codebase currently implements a **standard vector-based RAG pipeline**, which directly contradicts the PageIndex architecture you want. Here is exactly where:

### Problem 1: The entire `src/rag/` directory is traditional RAG

| File | What it does | Why it contradicts PageIndex |
|------|-------------|------------------------------|
| [`src/rag/embeddings.py`](src/rag/embeddings.py) | Loads a `SentenceTransformer` model (`bge-base-en-v1.5`) and generates 768-dim vector embeddings for text | PageIndex does NOT use embeddings. The LLM navigates a tree index instead of doing similarity search on vectors. |
| [`src/rag/chunker.py`](src/rag/chunker.py) | Splits documents into 512-character overlapping chunks | PageIndex explicitly has **no chunking** (red X in your diagram). It works at the page level. |
| [`src/rag/retriever.py`](src/rag/retriever.py) | Implements `HybridRetriever` with vector search + BM25 + Reciprocal Rank Fusion | PageIndex does not use vector search or BM25. It uses LLM-driven tree navigation. |
| [`src/rag/reranker.py`](src/rag/reranker.py) | Uses a cross-encoder model (`ms-marco-MiniLM-L-6-v2`) to rerank retrieved chunks | PageIndex does not need reranking because the LLM already reasons about which pages are relevant during tree traversal. |

**What to do:** These files need to be either removed or replaced with PageIndex equivalents:
- `embeddings.py` -- replace with tree index navigation logic
- `chunker.py` -- replace with page-level content extraction (no chunking)
- `retriever.py` -- replace with tree search that walks the hierarchical index
- `reranker.py` -- may not be needed at all, or repurpose for page-level relevance

### Problem 2: Qdrant vector store should not exist

[`src/vectorstore/qdrant_store.py`](src/vectorstore/qdrant_store.py) implements a full Qdrant vector database client. It creates collections with 768-dimension cosine similarity vectors, upserts embeddings, and does vector similarity search. This is the core of traditional RAG.

Your architecture diagram shows **Document Tree Store (JSON/SQLite)** and **Page Content Cache** instead. You need:
- A **tree index store** (JSON or SQLite) that holds the hierarchical document structure
- A **page content store** that holds the raw text of each page, keyed by document + page number

### Problem 3: The retriever node does vector search

[`src/agents/nodes/retriever_node.py`](src/agents/nodes/retriever_node.py) is the node inside your LangGraph that handles retrieval. Right now it:
1. Generates an embedding for the query (line 43)
2. Does vector search in Qdrant (line 48)
3. Reranks with cross-encoder (line 60)

This should instead be a **Tree Search Agent Node** that:
1. Loads the hierarchical tree index for the relevant document(s)
2. Uses the LLM to reason about which branch of the tree to follow
3. Navigates down the tree until it reaches the relevant page(s)
4. Returns full page content (not chunks)

### Problem 4: The ingestion pipeline builds embeddings instead of a tree index

[`src/ingestion/pipeline.py`](src/ingestion/pipeline.py) currently:
1. Extracts text from PDF (this part is fine)
2. **Chunks the text** using `SemanticChunker` (line 79) -- should not chunk
3. **Generates embeddings** for each chunk (line 89) -- should not embed
4. **Stores in Qdrant** vector database (line 106) -- should store in tree index

For PageIndex, the ingestion pipeline should:
1. Extract text from PDF page by page (the `PDFProcessor` already does this correctly)
2. **Build a hierarchical tree index** -- use the LLM to generate a table-of-contents-like structure from the page contents
3. **Store page content** in a page content store (JSON/SQLite)
4. **Store the tree index** in the document tree store

### Problem 5: Config references embedding/vector settings that do not apply

[`src/core/config.py`](src/core/config.py) has these settings that are traditional-RAG-specific:
- `embedding_model` (line 38)
- `embedding_dimension` (line 39)
- `reranker_model` (line 45)
- `qdrant_url`, `qdrant_api_key`, `qdrant_path` (lines 50-52)
- `chunk_size`, `chunk_overlap` (lines 58-59)
- `retrieval_top_k`, `rerank_top_k` (lines 64-65)

These should be replaced with PageIndex-specific settings like:
- `tree_store_path` (where to store the JSON/SQLite tree index)
- `page_content_path` (where to store page content)
- `tree_search_model` (which LLM to use for tree navigation, e.g., `openai/gpt-oss-120b` as shown in your diagram)
- `max_tree_depth` (how deep the tree can go)

### Problem 6: Docker Compose includes Qdrant

[`docker-compose.yaml`](docker-compose.yaml) runs a Qdrant container (lines 31-38). Since PageIndex does not use a vector database, this service is unnecessary. You might replace it with a simple SQLite volume or a lightweight JSON file store.

---

## Things That ARE Correct and Should Be Kept

Not everything needs to change. These parts align with your PageIndex architecture:

| Component | File | Why it is correct |
|-----------|------|-------------------|
| **FastAPI layer** | [`src/api/main.py`](src/api/main.py) | The API layer is architecture-agnostic. It works regardless of whether retrieval is vector-based or tree-based. |
| **Input Guardrails** | [`src/guardrails/input_guards.py`](src/guardrails/input_guards.py) | Prompt injection detection, PII masking, toxicity checks -- all still needed. |
| **Output Guardrails** | [`src/guardrails/output_guards.py`](src/guardrails/output_guards.py) | Hallucination checks, PII masking in responses -- still needed. |
| **Finance Compliance** | [`src/guardrails/finance_compliance.py`](src/guardrails/finance_compliance.py) | Investment advice detection, disclaimers, account number redaction -- still needed. |
| **Router Node** | [`src/agents/nodes/router_node.py`](src/agents/nodes/router_node.py) | Classifying query complexity (simple/standard/complex) is still useful for deciding how deep to search the tree. |
| **Planner Node** | [`src/agents/nodes/planner_node.py`](src/agents/nodes/planner_node.py) | Decomposing complex queries into sub-steps is still valid. |
| **Critic Node** | [`src/agents/nodes/critic_node.py`](src/agents/nodes/critic_node.py) | Evaluating retrieval quality and triggering retries is still valid (though it needs to evaluate page-level results instead of chunk-level). |
| **Generator Node** | [`src/agents/nodes/generator_node.py`](src/agents/nodes/generator_node.py) | Generating answers from context is still needed. The context will just be full pages instead of chunks. |
| **Guardrail Node** | [`src/agents/nodes/guardrail_node.py`](src/agents/nodes/guardrail_node.py) | Orchestrates input/output validation -- still needed. |
| **LangGraph Orchestrator** | [`src/agents/orchestrator.py`](src/agents/orchestrator.py) | The orchestrator pattern is correct. |
| **Graph structure** | [`src/agents/graphs/query_graph.py`](src/agents/graphs/query_graph.py) | The overall graph flow (input_guard -> router -> retrieval -> critic -> generator -> output_guard) is correct. The retrieval node just needs to be swapped from vector search to tree search. |
| **Groq LLM Client** | [`src/llm/groq_client.py`](src/llm/groq_client.py) | The LLM client is needed for all nodes. |
| **PDF Processor** | [`src/ingestion/pdf_processor.py`](src/ingestion/pdf_processor.py) | PyMuPDF extraction is still the first step. It already extracts page-by-page, which is exactly what PageIndex needs. |
| **Observability** | [`src/observability/`](src/observability/) | Tracing, metrics, logging -- all still needed. |
| **State Schema** | [`src/agents/schemas/state.py`](src/agents/schemas/state.py) | The `AgentState` TypedDict is mostly correct, though some fields like `query_embedding` and `reranked_docs` should be renamed/replaced. |

---

## Code-Level Bugs That Need Fixing (Regardless of RAG vs PageIndex)

These are bugs in the code that exist independent of the architecture choice. They will bite you no matter what.

### Bug 1: Graph routing -- fast_path never reaches `fast_generator`

**File:** [`src/agents/graphs/query_graph.py`](src/agents/graphs/query_graph.py:149)

**What happens:** Line 151 adds an unconditional edge:
```python
builder.add_edge("retriever", "critic")
```

This means ALL queries that go through the `retriever` node -- including simple queries routed to `fast_path` -- will then go to `critic`, and from `critic` to `generator`. The `fast_generator` node (line 113) is defined but **never reachable** because there is no edge leading to it.

**Why it matters:** Simple queries are supposed to skip the critic and use a faster, cheaper LLM model. Instead, they get the full expensive treatment.

**How to fix:** You need conditional routing after the retriever. For `fast_path`, the retriever should go directly to `fast_generator`. For `standard` and `planner` paths, it should go to `critic`. This requires tracking the route in the state and using a conditional edge after `retriever`.

### Bug 2: Streaming endpoint crashes at runtime

**File:** [`src/api/routes/query.py`](src/api/routes/query.py:60)

**What happens:** The streaming endpoint calls `chunk.model_dump_json()` on each chunk. But [`orchestrator.astream()`](src/agents/orchestrator.py:174) yields plain Python `dict` objects like `{"content": "...", "done": False}`. Plain dicts do not have a `.model_dump_json()` method.

**Why it matters:** Any call to `POST /api/v1/query/stream` will crash with `AttributeError: 'dict' object has no attribute 'model_dump_json'`.

**How to fix:** Either change `astream()` to yield Pydantic `StreamChunk` models, or change the route to use `json.dumps(chunk)` instead of `chunk.model_dump_json()`.

### Bug 3: Critic node swaps field mappings

**File:** [`src/agents/nodes/critic_node.py`](src/agents/nodes/critic_node.py:112-116)

**What happens:** The `_parse_evaluation` function maps JSON fields to the wrong `CriticEvaluation` attributes:
```python
groundedness_score=float(data.get("completeness_score", 0.5)),  # should be "groundedness_score"
completeness_score=float(data.get("confidence_score", 0.5)),    # should be "completeness_score"
```

The LLM is asked to output `relevance_score`, `completeness_score`, and `confidence_score`. But the code reads `completeness_score` and puts it into `groundedness_score`, and reads `confidence_score` and puts it into `completeness_score`.

**Why it matters:** The critic's evaluation scores are wrong, which means the retry logic (which depends on `relevance_score`) might make incorrect decisions about whether to retry retrieval.

**How to fix:** Map the JSON fields to the correct `CriticEvaluation` attributes, or change the prompt to output field names that match.

### Bug 4: `GroqClient` has no retry/backoff logic

**File:** [`src/llm/groq_client.py`](src/llm/groq_client.py)

**What happens:** Every LLM call goes directly to the Groq API with no error handling for transient failures. If Groq returns a 429 (rate limit), 503 (service unavailable), or times out, the entire query pipeline crashes.

**Why it matters:** Your system makes multiple LLM calls per query (router, possibly planner, critic, generator). With PageIndex, you will make even MORE LLM calls (tree navigation at each level). Without retry logic, any single failure kills the whole request.

**How to fix:** Add exponential backoff retry logic. You can use the `tenacity` library:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
```

### Bug 5: `GroqClient` is re-instantiated on every call

**Files:** [`router_node.py`](src/agents/nodes/router_node.py:42), [`critic_node.py`](src/agents/nodes/critic_node.py:70), [`generator_node.py`](src/agents/nodes/generator_node.py:62), [`planner_node.py`](src/agents/nodes/planner_node.py:47)

**What happens:** Every node creates `GroqClient()` fresh. Each instantiation creates new `Groq()` and `AsyncGroq()` HTTP client objects. A single query creates 3-4 separate HTTP clients.

**Why it matters:** Wasted resources, connection overhead, and you hit Groq's rate limits faster because each client tracks its own rate limit state independently.

**How to fix:** Make `GroqClient` a singleton, similar to how [`EmbeddingService`](src/rag/embeddings.py:20-26) already uses the singleton pattern with `_instance` and `__new__`.

### Bug 6: `IngestionPipeline.process()` is async but blocks the event loop

**File:** [`src/ingestion/pipeline.py`](src/ingestion/pipeline.py:47)

**What happens:** The method is declared `async def process(...)` but every operation inside it is synchronous -- PDF extraction, chunking, embedding, and storage all block. When called from the FastAPI async endpoint, this blocks the entire event loop, meaning no other requests can be served during ingestion.

**Why it matters:** If someone uploads a large PDF, the entire API becomes unresponsive until ingestion finishes.

**How to fix:** Either make it truly async (use `asyncio.to_thread()` for CPU-bound work) or remove the `async` keyword and run it in a background thread/task.

---

## Other Issues to Address

### Missing `.env.example`

The README says `cp .env.example .env` but no `.env.example` file exists. Anyone cloning the repo cannot figure out which environment variables are needed.

### README describes a completely different project

The README project structure shows `streamlit_app/`, `src/services/`, ChromaDB, `all-MiniLM-L6-v2` embeddings, etc. None of this exists in the actual codebase. The README needs a full rewrite.

### `.gitignore` references wrong artifacts

[`.gitignore`](.gitignore) includes `chroma_db/` (from the old stack) but not `qdrant_data/` or `checkpoints.db` (from the current stack). And if you move to PageIndex, you will need to ignore whatever local tree store files you create.

### CORS is wide open

[`src/api/main.py`](src/api/main.py:39) has `allow_origins=["*"]`. For a finance application, this should be restricted to known origins.

### No authentication

There is no auth on any endpoint. Anyone can query, ingest documents, or hit admin endpoints.

### Test coverage is minimal

[`tests/test_state.py`](tests/test_state.py) has 4 tests that only cover Pydantic model creation. There are zero tests for any node, any guardrail, the chunker, the API, or the graph routing logic.

### `ARCHITECTURE.md` has a broken image path

[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md:9) contains a Windows absolute path (`/c:/Users/lenovo/Downloads/...`). This is broken for everyone else.

---

## Prioritized Fix List

Here is what to do, in order:

### Phase 1: Fix bugs in existing code (do this NOW)

1. **Fix the graph routing bug** -- make `fast_path` actually reach `fast_generator`
2. **Fix the streaming endpoint** -- `dict` vs Pydantic model mismatch
3. **Fix the critic node field mapping** -- swapped `groundedness_score` / `completeness_score`
4. **Make `GroqClient` a singleton** -- stop re-instantiating on every call
5. **Add retry/backoff to `GroqClient`** -- handle transient Groq API failures
6. **Fix `IngestionPipeline.process()`** -- either make it truly async or remove `async`
7. **Add `.env.example`**
8. **Update `.gitignore`**

### Phase 2: Implement PageIndex (the core architecture change)

9. **Build the Tree Index Generator** -- given page-level text from `PDFProcessor`, use an LLM to generate a hierarchical tree index (TOC-like structure)
10. **Build the Tree Store** -- JSON or SQLite storage for the hierarchical index
11. **Build the Page Content Store** -- store raw page text keyed by (document, page_number)
12. **Build the Tree Search Agent Node** -- the new retriever that navigates the tree using LLM reasoning instead of vector similarity
13. **Update the ingestion pipeline** -- extract pages, build tree index, store pages (no chunking, no embedding)
14. **Update `AgentState`** -- replace `query_embedding`, `reranked_docs` with tree-search-specific fields
15. **Update config** -- replace embedding/vector/chunk settings with tree store settings
16. **Remove or archive `src/rag/`** -- embeddings, chunker, retriever, reranker are not needed for PageIndex
17. **Remove Qdrant** -- remove `src/vectorstore/`, remove Qdrant from `docker-compose.yaml`

### Phase 3: Harden for production

18. **Write tests** -- graph routing, guardrails, tree search, ingestion
19. **Rewrite the README** to match the actual PageIndex architecture
20. **Add authentication** to the API
21. **Restrict CORS** origins
22. **Pin dependency versions** in `requirements.txt`
23. **Fix the broken image path** in `ARCHITECTURE.md`

---

*Generated from a full codebase review on 2026-02-24.*
