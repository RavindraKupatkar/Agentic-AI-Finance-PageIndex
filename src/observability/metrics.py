"""
Prometheus Metrics - Application metrics

Exposes metrics for monitoring query latency, retrieval quality, etc.
"""

from prometheus_client import Counter, Histogram, Gauge, Info


# ─────────────────────────────────────────────
# APPLICATION METRICS
# ─────────────────────────────────────────────

# Query metrics
QUERY_COUNT = Counter(
    'rag_query_total',
    'Total number of RAG queries',
    ['status']  # success, error
)

QUERY_LATENCY = Histogram(
    'rag_query_latency_seconds',
    'Query latency in seconds',
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0]
)

TTFT = Histogram(
    'rag_time_to_first_token_seconds',
    'Time to first token in seconds',
    buckets=[0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
)

# Retrieval metrics
RETRIEVAL_COUNT = Counter(
    'rag_retrieval_total',
    'Total number of retrieval operations'
)

RETRIEVAL_LATENCY = Histogram(
    'rag_retrieval_latency_seconds',
    'Retrieval latency in seconds',
    buckets=[0.05, 0.1, 0.2, 0.3, 0.5, 1.0]
)

RELEVANCE_SCORE = Histogram(
    'rag_relevance_score',
    'Relevance scores from critic evaluation',
    buckets=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
)

# Generation metrics
GENERATION_LATENCY = Histogram(
    'rag_generation_latency_seconds',
    'LLM generation latency in seconds',
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

LLM_TOKENS = Counter(
    'rag_llm_tokens_total',
    'Total LLM tokens used',
    ['type']  # input, output
)

# Guardrail metrics
GUARDRAIL_BLOCKS = Counter(
    'rag_guardrail_blocks_total',
    'Number of requests blocked by guardrails',
    ['type']  # input, output
)

# Ingestion metrics
INGESTION_COUNT = Counter(
    'rag_ingestion_total',
    'Total number of ingestion operations',
    ['status']  # success, error
)

DOCUMENT_COUNT = Gauge(
    'rag_document_count',
    'Number of documents in vector store'
)

# System info
SYSTEM_INFO = Info(
    'rag_system',
    'RAG system information'
)


def setup_metrics():
    """Initialize metrics with default values"""
    SYSTEM_INFO.info({
        'version': '1.0.0',
        'environment': 'production',
        'vector_store': 'qdrant',
        'llm_provider': 'groq'
    })


def record_query_latency(latency_seconds: float):
    """Record query latency"""
    QUERY_LATENCY.observe(latency_seconds)


def record_ttft(ttft_seconds: float):
    """Record time to first token"""
    TTFT.observe(ttft_seconds)
