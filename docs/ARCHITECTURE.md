# 🏗️ Production Agentic RAG - System Architecture

> **Finance Chatbot with Multi-Agent RAG, <2s TTFT, and Production-Grade Observability**

---

## 📊 Architecture Diagram

![Production Agentic RAG Architecture](/c:/Users/lenovo/Downloads/Agentic%20finance%20document%20RAG/Finance%20RAG/docs/Production_Agentic_RAG_Architecture.png)

---

## 🔄 System Flow (Numbered Steps)

| Step | From | To | Description |
|------|------|-----|-------------|
| **1** | User | FastAPI | User sends query via REST API or Streamlit UI |
| **2** | FastAPI | Input Guardrails | Request validation, authentication, rate limiting |
| **3** | Input Guardrails | LangGraph Orchestrator | Sanitized query after PII masking, injection detection |
| **4** | Router Node | Hybrid Retrieval | Query routing based on complexity (simple/standard/complex) |
| **5** | Hybrid Retrieval | Groq LLM | Context from vector search + BM25 + reranking |
| **6** | Groq LLM | Generator Node | Streamed LLM response generation |
| **7** | Critic Node | Retriever Node | Self-correction loop if relevance < threshold |
| **8** | Generator Node | Output Guardrails | Raw response for compliance validation |
| **9** | Output Guardrails | Qdrant | Store interaction for future retrieval |
| **10** | Output Guardrails | RAGAS Evaluation | Sample evaluation for quality metrics |
| **11** | Memory | LangGraph Orchestrator | Conversation context from thread |
| **12** | FastAPI | User | Final response with disclaimers |
| **13-15** | Ingestion Pipeline | Qdrant | PDF → Chunks → Embeddings → Vector Store |

---

## 🧩 Component Details

### 🔵 API Layer (FastAPI)

```
src/api/
├── main.py          # Application entry point
├── routes/
│   ├── query.py     # POST /api/v1/query, /query/stream
│   ├── ingest.py    # POST /api/v1/ingest
│   ├── health.py    # GET /health, /ready, /live
│   └── admin.py     # System administration
├── schemas/         # Pydantic request/response models
└── middleware/      # Tracing, rate limiting
```

**Endpoints:**
- `POST /api/v1/query` - Synchronous RAG query
- `POST /api/v1/query/stream` - Streaming response (SSE)
- `POST /api/v1/ingest` - Document ingestion
- `GET /health` - Basic health check
- `GET /ready` - Kubernetes readiness probe
- `GET /metrics` - Prometheus metrics

---

### 🔴 Input Guardrails

```
src/guardrails/input_guards.py
```

| Guard | Purpose | Action |
|-------|---------|--------|
| **Prompt Injection** | Detect malicious prompts | Block request |
| **Toxicity** | Filter inappropriate content | Block request |
| **PII Detection** | Find sensitive data | Mask in query |
| **Input Length** | Prevent overflow | Truncate |

**Libraries:** `llm-guard`, regex patterns, custom validators

---

### 💜 LangGraph Multi-Agent Orchestrator

```
src/agents/
├── orchestrator.py          # Main entry point
├── schemas/state.py         # AgentState TypedDict
├── graphs/query_graph.py    # StateGraph definition
└── nodes/
    ├── router_node.py       # Query complexity classification
    ├── planner_node.py      # Complex query decomposition
    ├── retriever_node.py    # Hybrid search + reranking
    ├── critic_node.py       # Retrieval quality evaluation
    ├── generator_node.py    # LLM response generation
    └── guardrail_node.py    # Input/output validation
```

**State Schema (TypedDict):**
```python
class AgentState(TypedDict):
    question: str
    thread_id: str
    query_type: Literal["simple", "standard", "complex", "multi_hop"]
    messages: Annotated[Sequence[BaseMessage], add_messages]
    retrieved_docs: List[dict]
    reranked_docs: List[dict]
    relevance_score: float
    needs_retry: bool
    retry_count: int
    answer: Optional[str]
    sources: List[str]
    confidence: float
```

**Graph Flow:**
```
START → input_guard → router
           ├── [simple] → retriever → fast_generator → output_guard → END
           ├── [standard] → retriever → critic → generator → output_guard → END
           └── [complex] → planner → retriever → critic ←─── retry loop
                                          └── generator → output_guard → END
```

---

### 🟢 RAG Pipeline

```
src/rag/
├── embeddings.py    # BGE-base-en-v1.5 (768 dim)
├── retriever.py     # Hybrid: Vector + BM25
├── reranker.py      # Cross-encoder reranking
└── chunker.py       # Semantic chunking
```

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Embeddings** | `bge-base-en-v1.5` | 768-dim dense vectors |
| **Vector Search** | Qdrant HNSW | Semantic similarity |
| **Keyword Search** | BM25 | Exact term matching |
| **Reranker** | Cross-Encoder | Precision improvement |

**Hybrid Retrieval Strategy:**
1. Over-fetch 20 docs from Qdrant
2. Apply BM25 keyword scoring
3. Reciprocal Rank Fusion (RRF)
4. Rerank top-10 with cross-encoder
5. Return top-5 for context

---

### 🟢 Groq LLM Service

```
src/llm/groq_client.py
```

| Model | Use Case | TTFT |
|-------|----------|------|
| `llama-3.1-8b-instant` | Simple queries, routing | ~80ms |
| `gemma2-9b-it` | Medium complexity | ~120ms |
| `llama-3.3-70b-versatile` | Complex reasoning | ~200ms |
| `mixtral-8x7b-32768` | Long context (32K) | ~150ms |

**Features:**
- Async streaming API
- Automatic model selection based on complexity
- Rate limit handling with exponential backoff

---

### 🟢 Vector Store (Qdrant)

```
src/vectorstore/qdrant_store.py
```

- **Mode:** Self-hosted (Docker) or embedded
- **Distance:** Cosine similarity
- **Indexing:** HNSW with 768 dimensions
- **Filtering:** Source-based, metadata queries

---

### 🔴 Output Guardrails & Finance Compliance

```
src/guardrails/
├── output_guards.py        # Hallucination, PII
└── finance_compliance.py   # Domain-specific rules
```

| Guard | Purpose |
|-------|---------|
| **Hallucination Check** | Verify grounding in context |
| **PII Masking** | Remove leaked sensitive data |
| **Investment Advice Detection** | Flag prohibited phrases |
| **Disclaimer Injection** | Add regulatory notices |
| **Account Number Redaction** | Mask financial identifiers |

---

### 📊 Observability Stack

```
src/observability/
├── tracing.py     # OpenTelemetry → Tempo
├── metrics.py     # Prometheus counters/histograms
└── logging.py     # Structlog JSON logging
```

| Tool | Purpose | Port |
|------|---------|------|
| **OpenTelemetry + Tempo** | Distributed tracing | 4317 |
| **Prometheus** | Metrics collection | 9090 |
| **Grafana** | Dashboards | 3000 |
| **Phoenix (Arize)** | LLM observability | 6006 |
| **Structlog** | JSON structured logs | - |

**Key Metrics:**
- `rag_query_latency_seconds` - TTFT tracking
- `rag_relevance_score` - Retrieval quality
- `rag_guardrail_blocks_total` - Security events
- `rag_ingestion_total` - Document processing

---

### 📈 RAGAS Evaluation

Continuous evaluation sampling:

| Metric | Description |
|--------|-------------|
| **Faithfulness** | Is answer grounded in context? |
| **Answer Relevancy** | Does answer address the question? |
| **Context Precision** | Are retrieved docs relevant? |
| **Context Recall** | Was all needed info retrieved? |

---

### 🔷 Ingestion Pipeline

```
src/ingestion/
├── pipeline.py        # Orchestration
└── pdf_processor.py   # PyMuPDF extraction
```

**Flow:**
1. **Extract** - PyMuPDF text extraction
2. **Chunk** - Semantic chunking (512 chars, 50 overlap)
3. **Embed** - Batch BGE embedding
4. **Store** - Upsert to Qdrant with metadata

---

### ⬛ Infrastructure

```
├── Dockerfile            # Production image
├── docker-compose.yaml   # Full stack
└── infra/
    ├── prometheus.yaml
    ├── tempo.yaml
    ├── otel-collector-config.yaml
    └── grafana/provisioning/
```

**Docker Services:**
- `app` - FastAPI application
- `qdrant` - Vector database
- `prometheus` - Metrics
- `grafana` - Dashboards
- `tempo` - Tracing
- `otel-collector` - Telemetry pipeline
- `phoenix` - LLM observability

---

## 🚀 Quick Start

```bash
# 1. Start infrastructure
docker-compose up -d qdrant prometheus grafana tempo phoenix

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Add GROQ_API_KEY

# 4. Run application
python main.py server

# 5. Ingest documents
python main.py ingest ./data/financial_report.pdf

# 6. Query
python main.py query "What is the Q4 revenue?"
```

---

## 📍 Service URLs

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Metrics | http://localhost:8000/metrics |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Phoenix | http://localhost:6006 |
| Qdrant | http://localhost:6333 |

---

## 🎯 Latency Budget (<2s TTFT)

```
┌─────────────────────────────────────────────────────┐
│ Input Validation:       ~30ms                       │
│ Embedding Query:        ~50ms                       │
│ Qdrant Search:          ~80ms                       │
│ Reranking:              ~100ms                      │
│ Context Preparation:    ~40ms                       │
│ Network to Groq:        ~100ms                      │
│ Groq TTFT:              ~80-200ms                   │
├─────────────────────────────────────────────────────┤
│ TOTAL TTFT:             ~480-600ms ✅               │
└─────────────────────────────────────────────────────┘
```

---

## 📋 Technology Stack

| Category | Technology |
|----------|------------|
| **Framework** | LangGraph, FastAPI |
| **LLM** | Groq (Free Tier) |
| **Embeddings** | BGE-base-en-v1.5 |
| **Vector DB** | Qdrant |
| **Guardrails** | LLM Guard, Custom |
| **Tracing** | OpenTelemetry, Tempo |
| **Metrics** | Prometheus, Grafana |
| **LLM Observability** | Phoenix (Arize) |
| **Evaluation** | RAGAS |
| **Infrastructure** | Docker, K8s-ready |
