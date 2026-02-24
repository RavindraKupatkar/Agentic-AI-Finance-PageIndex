# Codebase Review -- Things to Keep in Mind Before Moving Forward

This document captures findings from a full review of the repository. It is organized into **critical blockers**, **architectural concerns**, **code-level issues**, and **nice-to-haves** so you can prioritize work accordingly.

---

## 1. Critical Blockers (fix before any feature work)

### 1.1 Missing `.env.example` file

The README references `cp .env.example .env`, but no `.env.example` exists in the repo. Anyone cloning the project has no idea which environment variables are required. At minimum it should contain:

```
GROQ_API_KEY=
QDRANT_URL=
QDRANT_API_KEY=
OTLP_ENDPOINT=
ENV=development
```

### 1.2 `GroqClient` instantiated per-call -- no singleton, no connection reuse

Every node (`router_node`, `critic_node`, `generator_node`) creates a fresh `GroqClient()` on each invocation. That means a new `Groq` + `AsyncGroq` HTTP client is created per graph invocation -- multiple times per query. This adds latency and risks hitting Groq's rate limits faster.

**Where:** [`GroqClient.__init__()`](src/llm/groq_client.py:22), called from [`router_node.classify_query()`](src/agents/nodes/router_node.py:42), [`critic_node.evaluate_retrieval()`](src/agents/nodes/critic_node.py:70), [`generator_node.generate_response()`](src/agents/nodes/generator_node.py:62)

**Suggestion:** Make `GroqClient` a singleton (like the pattern already used for `_query_graph` in [`query_graph.py`](src/agents/graphs/query_graph.py:183)), or inject it via the graph state/config.

### 1.3 No error handling / retry logic in `GroqClient`

The architecture doc mentions "Rate limit handling with exponential backoff," but [`groq_client.py`](src/llm/groq_client.py) has zero retry logic. Any transient Groq API failure (rate limit 429, timeout, 5xx) will crash the entire query pipeline.

**Suggestion:** Add `tenacity` or manual retry with exponential backoff, especially for 429 responses.

### 1.4 Graph routing bug -- fast_path still goes through critic

In [`query_graph.py`](src/agents/graphs/query_graph.py:149-151), the `retriever` node has an unconditional edge to `critic`:

```python
builder.add_edge("retriever", "critic")
```

This means queries routed to `fast_path` (simple queries) also go through the critic node instead of going directly to `fast_generator`. The `fast_generator` node is defined but never actually reachable because all retriever output flows into `critic`, which then flows into `generator` (not `fast_generator`).

**Impact:** Simple queries get the full standard-path treatment, defeating the purpose of the fast path optimization.

### 1.5 Test coverage is minimal

There is exactly one test file ([`tests/test_state.py`](tests/test_state.py)) with 4 tests that only cover Pydantic models and state creation. Zero tests for:

- Any graph node logic
- Guardrails (input/output)
- The ingestion pipeline
- API endpoints
- The chunker
- The retriever

You should not add features on top of untested code. Prioritize at least unit tests for guardrails, chunker, and the graph routing logic.

---

## 2. Architectural Concerns

### 2.1 README describes a different project structure than what exists

The README project tree references `streamlit_app/`, `src/config.py`, `src/main.py`, `src/services/`, `src/models/`, `src/graphs/nodes.py`, and ChromaDB. The actual codebase uses FastAPI, Qdrant, a multi-node agent graph, etc. The README is from an earlier version of the project and is now misleading.

**Suggestion:** Rewrite the README to reflect the current architecture, or at least remove the outdated project structure block.

### 2.2 Hybrid retrieval (BM25) is not implemented

The architecture doc and `HybridRetriever` class in [`retriever.py`](src/rag/retriever.py:53) explicitly state:

```python
# TODO: Add BM25 keyword search and RRF fusion
```

The `_reciprocal_rank_fusion` method exists but is never called. Meanwhile, `retriever_node.py` bypasses `HybridRetriever` entirely and calls `QdrantStore` and `CrossEncoderReranker` directly.

**Impact:** The system only does vector search + reranking, not the hybrid search described in the docs.

### 2.3 `EmbeddingService` and `QdrantStore` are re-instantiated per call

Similar to the `GroqClient` issue, [`retriever_node.py`](src/agents/nodes/retriever_node.py:42-47) creates new `EmbeddingService()` and `QdrantStore()` on every retrieval call. Loading a sentence-transformer model from scratch each time is very expensive.

**Suggestion:** Make these singletons or use dependency injection. `EmbeddingService` especially should load the model once.

### 2.4 CORS is wide open

[`src/api/main.py`](src/api/main.py:37-43) has `allow_origins=["*"]`. This is fine for local development, but a production finance application should restrict origins.

### 2.5 No authentication or authorization

The API has rate limiting middleware but no auth. Any client can query, ingest documents, or hit admin endpoints. For a finance-domain application, this is a significant gap.

### 2.6 `docker-compose.yaml` uses deprecated `version` key

Docker Compose V2 ignores the `version` field. It is not harmful but generates deprecation warnings.

---

## 3. Code-Level Issues

### 3.1 Streaming endpoint serializes dicts, not Pydantic models

In [`query.py`](src/api/routes/query.py:60), the stream endpoint calls `chunk.model_dump_json()`, but `orchestrator.astream()` yields plain `dict` objects (not Pydantic models), so this will raise an `AttributeError` at runtime.

### 3.2 `_parse_evaluation` maps fields incorrectly in critic node

In [`critic_node.py`](src/agents/nodes/critic_node.py:112-116):

```python
CriticEvaluation(
    relevance_score=float(data.get("relevance_score", 0.5)),
    groundedness_score=float(data.get("completeness_score", 0.5)),  # wrong mapping
    completeness_score=float(data.get("confidence_score", 0.5)),    # wrong mapping
    ...
)
```

`groundedness_score` is being set from the JSON's `completeness_score`, and `completeness_score` from `confidence_score`. The field names are swapped.

### 3.3 `.gitignore` references `chroma_db/` but the project uses Qdrant

The `.gitignore` still references `chroma_db/` from the old stack. It should include `qdrant_data/`, `checkpoints.db`, and any other artifacts the current stack produces.

### 3.4 `Chunk` dataclass has mutable default argument

In [`chunker.py`](src/rag/chunker.py:21):

```python
metadata: dict = None
```

This is fine with `None`, but if it were `{}` it would be a classic mutable default bug. Consider using `field(default_factory=dict)` for clarity and safety.

### 3.5 PII regex overlap between SSN and phone patterns

In [`input_guards.py`](src/api/../src/guardrails/input_guards.py:118-129), the phone regex `\b\d{3}[-.]?\d{3}[-.]?\d{4}\b` and SSN regex `\b\d{3}[-]?\d{2}[-]?\d{4}\b` can match overlapping patterns. For example, a 10-digit phone number could be partially matched as an SSN. The SSN regex should be more specific (e.g., require dashes or known SSN ranges).

### 3.6 `IngestionPipeline.process()` is async but contains no awaits

[`pipeline.py:process()`](src/ingestion/pipeline.py:47) is declared `async` but all operations inside it are synchronous. This blocks the event loop during PDF extraction, embedding generation, and vector storage. Either make the internals truly async or remove the `async` declaration.

---

## 4. Configuration and Infrastructure

### 4.1 Pinned dependency versions are too loose

[`requirements.txt`](requirements.txt) uses `>=` for all packages. This means `pip install` on two different machines at different times can produce completely different dependency trees. Pin exact versions (or use a lockfile like `pip-compile` / `poetry.lock`).

### 4.2 No health check for Qdrant in `docker-compose.yaml`

The `app` service `depends_on: qdrant`, but without a health check, Docker starts the app as soon as the Qdrant container starts (not when Qdrant is actually ready to accept connections). Add a health check to the Qdrant service.

### 4.3 Grafana admin password is hardcoded

In [`docker-compose.yaml`](docker-compose.yaml:82), `GF_SECURITY_ADMIN_PASSWORD=admin` is hardcoded. Use an environment variable.

### 4.4 No `ARCHITECTURE.md` image path fix

[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md:9) contains a Windows absolute path:

```
/c:/Users/lenovo/Downloads/Agentic%20finance%20document%20RAG/...
```

This image link is broken for anyone else. Use a relative path.

---

## 5. Recommendations Before Moving Forward

Here is a prioritized checklist:

1. **Fix the graph routing bug** (fast_path never reaches `fast_generator`) -- this is a logic error in the core pipeline
2. **Add `.env.example`** -- unblocks onboarding for any new contributor
3. **Make `GroqClient`, `EmbeddingService`, `QdrantStore` singletons** -- addresses latency, memory, and rate-limit concerns
4. **Add retry/backoff to `GroqClient`** -- production readiness
5. **Fix the streaming endpoint** (`dict` vs Pydantic model mismatch)
6. **Fix the critic node field mapping** -- correctness of evaluation scores
7. **Write tests** for graph routing, guardrails, chunker, and at least one integration test for the query pipeline
8. **Update the README** to match the actual project structure
9. **Implement BM25 hybrid search** or remove it from the docs to avoid confusion
10. **Pin dependency versions** and add a lockfile
11. **Add authentication** to the API layer
12. **Restrict CORS** origins for production

---

*Generated from a full codebase review on 2026-02-24.*
