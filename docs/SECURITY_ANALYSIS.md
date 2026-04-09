# Security Analysis: Agentic-AI-Finance-PageIndex

**Date:** 2026-02-24
**Scope:** Full codebase review -- backend, frontend, infrastructure, and agent pipeline
**Branch:** `MVP-1`

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Security Bugs](#critical-security-bugs)
3. [High-Severity Issues](#high-severity-issues)
4. [Medium-Severity Issues](#medium-severity-issues)
5. [Low-Severity Issues](#low-severity-issues)
6. [Implementation Challenges](#implementation-challenges)
7. [Future Threats](#future-threats)
8. [Recommendations Summary](#recommendations-summary)

---

## Executive Summary

This repository implements a Finance Agentic RAG system using LangGraph, Groq LLM, and a novel "PageIndex" tree-based retrieval approach. After a thorough review, **4 critical**, **5 high**, **6 medium**, and **4 low** severity issues were identified spanning secrets management, API security, prompt injection resilience, infrastructure hardening, and LLM-specific attack vectors.

The system has solid foundations in some areas (parameterized SQL queries, PDF magic-byte validation, input guardrails), but has significant gaps that would need to be addressed before any production deployment.

---

## Critical Security Bugs

### CRIT-01: Hardcoded API Key in `.env.example`

**File:** [`.env.example`](.env.example:8)
**Line:** 8

```
GROQ_API_KEY=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
```

**Description:** The `.env.example` file contains what appears to be a real Groq API key (prefix `gsk_` matches the Groq key format). Example files are meant to contain placeholder values like `your-api-key-here`, not actual secrets. Since this file is committed to version control, the key is exposed to anyone with repository access.

**Impact:** Unauthorized use of the Groq API under the owner's account, potential billing abuse, and credential stuffing if the same key pattern is reused elsewhere.

**Remediation:**
1. Immediately rotate the Groq API key at https://console.groq.com
2. Replace the value with a placeholder: `GROQ_API_KEY=your-groq-api-key-here`
3. Add a pre-commit hook using tools like `detect-secrets` or `gitleaks` to prevent future leaks
4. Audit git history with `git log -S "gsk_"` to verify the key hasn't been in other files

---

### CRIT-02: Wildcard CORS -- Full Open Access

**File:** [`src/api/main.py`](src/api/main.py:44)
**Lines:** 44-50

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Description:** The API allows requests from any origin with full credentials. This is a textbook misconfiguration. Combined with `allow_credentials=True`, this violates the CORS spec (browsers should reject `*` with credentials, but intermediary proxies or non-browser clients won't enforce this) and opens the door to cross-site request forgery from any domain.

**Impact:** Any malicious website can make authenticated requests to the API if a user's browser has active sessions. Attackers can exfiltrate conversation data, query telemetry, and trigger document ingestion.

**Remediation:**
```python
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
```

---

### CRIT-03: No Authentication or Authorization

**Files:** [`src/api/routes/pageindex.py`](src/api/routes/pageindex.py:168), [`src/api/routes/conversations.py`](src/api/routes/conversations.py:46)

**Description:** Every API endpoint is publicly accessible with zero authentication. There is no auth middleware, no API key validation, no JWT verification, and no session management anywhere in the codebase. The telemetry and conversation endpoints expose potentially sensitive financial query data to any caller.

Specific unauthenticated endpoints of concern:
- `GET /api/v1/pageindex/telemetry` -- exposes all user queries and internal system metrics
- `GET /api/v1/conversations` -- exposes all conversation history
- `DELETE /api/v1/conversations/{id}` -- allows anyone to delete conversations
- `POST /api/v1/pageindex/ingest` -- allows anyone to upload PDFs
- `GET /metrics` -- Prometheus metrics are world-readable

**Impact:** Complete data exposure. Any attacker can read all user queries, financial document contents, conversation history, and system telemetry. They can also inject malicious PDFs and delete data.

**Remediation:**
1. Add API key authentication as a minimum (FastAPI `Depends` with header validation)
2. Implement role-based access for admin endpoints (telemetry, metrics)
3. Add rate limiting per authenticated user, not just IP
4. Consider OAuth2/OIDC for production deployments

---

### CRIT-04: Grafana Default Admin Credentials + Anonymous Access

**File:** [`docker-compose.yaml`](docker-compose.yaml:81)
**Lines:** 81-83

```yaml
environment:
  - GF_SECURITY_ADMIN_PASSWORD=admin
  - GF_AUTH_ANONYMOUS_ENABLED=true
```

**Description:** Grafana is deployed with the default `admin/admin` credentials and anonymous access enabled. Anyone with network access to port 3000 can view all dashboards, query data sources, and modify configurations.

**Impact:** Full access to observability data, potential pivot to other services through Grafana data source configurations.

**Remediation:**
- Use a strong password from an environment variable: `GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}`
- Disable anonymous access: `GF_AUTH_ANONYMOUS_ENABLED=false`
- Restrict Grafana to internal network only (remove port mapping or use reverse proxy)

---

## High-Severity Issues

### HIGH-01: Rate Limiter Bypasses and Memory Leak

**File:** [`src/api/middleware/rate_limit.py`](src/api/middleware/rate_limit.py:12)

**Description:** The rate limiter has three issues:

1. **Not actually enabled.** The `RateLimitMiddleware` is defined but never added to the FastAPI app in [`src/api/main.py`](src/api/main.py:52). Only `TracingMiddleware` is registered.

2. **IP spoofing bypass.** The limiter uses `request.client.host` which reflects the direct connection IP. Behind a reverse proxy (common in production), this will be the proxy's IP, not the user's. All users would share one rate limit bucket, or an attacker behind a different proxy gets unlimited access.

3. **Unbounded memory growth.** `self.request_counts` is a `defaultdict(list)` that grows indefinitely. Old IPs are only cleaned when they make new requests. A distributed attack from millions of unique IPs would consume unbounded memory.

**Impact:** No rate limiting protection in practice. DDoS potential. Memory exhaustion over time.

**Remediation:**
- Actually register the middleware: `app.add_middleware(RateLimitMiddleware)`
- Use `X-Forwarded-For` or `X-Real-IP` headers with proper trusted proxy configuration
- Use a bounded data structure (e.g., LRU cache) or external store (Redis) for rate limit state
- Add periodic cleanup of stale entries

---

### HIGH-02: Guardrail Fail-Open Design

**File:** [`src/agents/nodes/guardrail_node.py`](src/agents/nodes/guardrail_node.py:198)
**Lines:** 198-202

```python
# Fail open -- let the query through on guardrail failure
return {
    "input_valid": True,
    "guardrail_warnings": [f"Input guard error: {str(exc)}"],
}
```

**Description:** When the input guardrail encounters any exception, it fails open and allows the query to proceed through the pipeline. This means if an attacker can trigger an exception in the guardrail logic (e.g., via regex catastrophic backtracking on the PII patterns, or unexpected input encoding), all protections are bypassed.

The same pattern exists in [`validate_output()`](src/agents/nodes/guardrail_node.py:304) at line 314:
```python
return {"output_valid": True, "guardrail_warnings": warnings}
```

**Impact:** Guardrail bypass through crafted inputs. PII leakage if output guard fails. Prompt injection if input guard fails.

**Remediation:**
- Fail closed by default: if guardrails error out, reject the query
- Add circuit-breaker logic: if guardrails fail N times in a row, enter a degraded state
- Wrap regex operations in timeout protection to prevent ReDoS

---

### HIGH-03: Path Traversal in File Upload (Filename Injection)

**File:** [`src/api/routes/pageindex.py`](src/api/routes/pageindex.py:311)
**Line:** 311

```python
pdf_path = pdfs_dir / file.filename
```

**Description:** The uploaded filename is used directly to construct the file path without sanitization. An attacker could upload a file with a name like `../../etc/cron.d/malicious.pdf` or `../src/api/main.py` to write files outside the intended `data/pdfs/` directory. While the `.pdf` extension check exists, the path traversal happens before it's written.

**Impact:** Arbitrary file write on the server filesystem (limited to files ending in `.pdf`, but could overwrite existing PDFs or place files in unexpected locations).

**Remediation:**
```python
from pathlib import PurePosixPath
safe_name = PurePosixPath(file.filename).name  # strips directory components
if not safe_name or not safe_name.lower().endswith(".pdf"):
    raise HTTPException(status_code=400, detail="Invalid filename")
pdf_path = pdfs_dir / safe_name
```

---

### HIGH-04: Sensitive Internal State Exposed in Error Responses

**File:** [`src/api/routes/pageindex.py`](src/api/routes/pageindex.py:272)
**Line:** 272

```python
raise HTTPException(status_code=500, detail=str(exc))
```

This pattern appears in multiple places:
- [`pageindex.py:381`](src/api/routes/pageindex.py:381)
- [`pageindex.py:407`](src/api/routes/pageindex.py:407)
- [`pageindex.py:436`](src/api/routes/pageindex.py:436)
- [`health.py:41`](src/api/routes/health.py:41) -- `f"unhealthy: {e}"`

**Description:** Raw exception messages (including stack traces, file paths, and internal state) are returned directly to API callers. This leaks implementation details that help attackers map the system.

**Impact:** Information disclosure -- internal file paths, database schema details, library versions, and configuration values could be exposed through error messages.

**Remediation:**
- Return generic error messages to clients: `"An internal error occurred"`
- Log the full exception server-side for debugging
- Use a custom exception handler that sanitizes responses in production

---

### HIGH-05: Exposed Internal Services in Docker Compose

**File:** [`docker-compose.yaml`](docker-compose.yaml:31)

**Description:** Multiple internal-only services have their ports mapped to the host:
- Qdrant: `6333:6333` and `6334:6334` (vector DB with no auth)
- OTEL Collector: `4317:4317`, `4318:4318`, `8888:8888`
- Tempo: `3200:3200`, `14268:14268`
- Prometheus: `9090:9090`
- Phoenix: `6006:6006`

None of these services have authentication configured.

**Impact:** Direct access to the vector database (read/write/delete), tracing data, metrics, and LLM observability data from any network-adjacent attacker.

**Remediation:**
- Remove host port mappings for internal services; use Docker networking only
- If external access is needed, put them behind an authenticated reverse proxy
- Use Docker Compose `internal: true` network flag for services that don't need external access

---

## Medium-Severity Issues

### MED-01: Prompt Injection Guardrails Are Keyword-Based Only

**File:** [`src/agents/nodes/guardrail_node.py`](src/agents/nodes/guardrail_node.py:38)
**Lines:** 38-51

```python
_INJECTION_SIGNATURES = [
    "ignore previous instructions",
    "ignore all instructions",
    ...
    "jailbreak",
]
```

**Description:** The prompt injection detection relies on a static list of 12 keyword patterns matched via simple substring search. This is trivially bypassed with:
- Unicode homoglyphs: `ignоre previоus instructiоns` (Cyrillic "о" instead of Latin "o")
- Whitespace injection: `ignore  previous  instructions`
- Encoding tricks: base64-encoded payloads in the question
- Indirect injection: "What does the phrase 'ignore previous instructions' mean?"
- Multi-language attacks: translating attack phrases to other languages
- Token splitting: `ig nore pre vious in structions`

**Impact:** Prompt injection bypass leading to LLM manipulation, data exfiltration through crafted prompts, or generation of harmful financial advice.

**Remediation:**
- Add an LLM-based injection classifier (a small model trained on injection detection)
- Use fuzzy matching or embedding similarity for injection detection
- Normalize Unicode and whitespace before checking
- Consider integrating `llm-guard` (already in requirements.txt as optional)
- Implement output-side injection detection (check if the LLM response contains instructions)

---

### MED-02: SQLite Databases Accessible Without Encryption

**Files:** [`src/observability/telemetry.py`](src/observability/telemetry.py:170), [`src/observability/conversations.py`](src/observability/conversations.py:75), [`src/pageindex/tree_store.py`](src/pageindex/tree_store.py:162)

**Description:** Three SQLite databases (`telemetry.db`, `conversations.db`, `pageindex_metadata.db`) store sensitive data including user queries, conversation history, financial document metadata, and full query answers. All are stored unencrypted on disk with no access controls beyond filesystem permissions.

The databases are also committed to the repository: [`data/conversations.db`](data/conversations.db), [`data/pageindex_metadata.db`](data/pageindex_metadata.db), [`data/telemetry.db`](data/telemetry.db) are all in the tracked files.

**Impact:** Anyone with filesystem or repository access can read all user queries, financial data, and conversation history.

**Remediation:**
- Add `data/*.db` to `.gitignore`
- Use SQLCipher for encryption at rest in production
- Implement data retention policies (auto-purge after N days)
- Ensure database files have restrictive permissions (600)

---

### MED-03: No Input Validation on Conversation Endpoints

**File:** [`src/api/routes/conversations.py`](src/api/routes/conversations.py:32)

**Description:** The `AddMessageRequest` accepts any string for `role` without validation. While the DB uses parameterized queries (preventing SQL injection), there's no constraint ensuring `role` is one of `"user"` or `"assistant"`. Similarly, `content` has no length limit, enabling storage of arbitrarily large payloads.

The `list_conversations` `limit` parameter also has no upper bound -- a caller could request `limit=999999999`.

**Impact:** Data integrity issues, potential storage abuse, and unexpected behavior in frontend rendering.

**Remediation:**
```python
class AddMessageRequest(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=50000)
```

---

### MED-04: PII Patterns Have False Positives and Gaps

**File:** [`src/agents/nodes/guardrail_node.py`](src/agents/nodes/guardrail_node.py:30)
**Lines:** 30-36

**Description:** The PII detection patterns have issues:
- The phone pattern `\b\d{3}[\s.-]?\d{3}[\s.-]?\d{4}\b` matches many financial numbers (e.g., "Revenue was 123.456.7890 million")
- No detection for: passport numbers, bank account/routing numbers, IBAN, tax IDs (non-US), or physical addresses
- Credit card pattern `\b\d{16}\b` won't match cards with spaces or dashes (though the second pattern partially covers this)
- Financial documents commonly contain numbers that overlap with PII patterns

**Impact:** Over-masking legitimate financial data in queries; under-detecting actual PII from non-US formats.

**Remediation:**
- Use a dedicated PII detection library (e.g., `presidio-analyzer` from Microsoft)
- Add Luhn checksum validation for credit card numbers
- Implement context-aware PII detection that considers surrounding text
- Add configurable PII sensitivity levels

---

### MED-05: Unpinned Dependency Versions

**File:** [`requirements.txt`](requirements.txt:1)

**Description:** All dependencies use `>=` minimum version constraints with no upper bound. For example:
```
fastapi>=0.109.0
langgraph>=0.0.40
groq>=0.4.0
torch>=2.1.0
```

This means `pip install` could pull in any future major version, which may introduce breaking changes or, worse, supply chain compromises.

**Impact:** Build reproducibility issues, potential introduction of vulnerable or malicious dependency versions.

**Remediation:**
- Pin exact versions in a lock file: `pip freeze > requirements.lock`
- Use `pip-compile` (pip-tools) or Poetry for deterministic builds
- Set up Dependabot or Renovate for automated dependency update PRs
- Add hash verification: `pip install --require-hashes`

---

### MED-06: Frontend Hardcoded API URL

**File:** [`frontend/src/api/client.js`](frontend/src/api/client.js:3)

```javascript
const API_BASE = 'http://127.0.0.1:8000/api/v1';
```

**Description:** The API base URL is hardcoded to `http://127.0.0.1:8000` (plain HTTP, localhost only). This means:
- No HTTPS in any environment
- Cannot deploy frontend separately from backend
- No environment-based configuration

**Impact:** All API traffic is unencrypted; credentials and financial data transmitted in plaintext.

**Remediation:**
```javascript
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1';
```

---

## Low-Severity Issues

### LOW-01: `.gitignore` Missing Coverage for Database and Sensitive Files

**File:** [`.gitignore`](.gitignore:1)

**Description:** The `.gitignore` does not exclude:
- `data/*.db` (SQLite databases with user data)
- `data/*.pdf` (potentially sensitive financial documents)
- `data/*.har` (HTTP archive with request/response data -- [`data/localhost.har`](data/localhost.har) is tracked)
- `data/trees/*.json` (tree indexes containing document structure)

**Impact:** Sensitive financial documents and user data are committed to version control.

---

### LOW-02: Docker Container Runs pip as Root Before User Switch

**File:** [`Dockerfile`](Dockerfile:16)

**Description:** The `pip install` command runs as root (line 16), and the non-root user is created afterward (line 23). While the final process runs as `appuser`, the installed packages were written by root, and any post-install scripts ran with root privileges.

**Remediation:** Use multi-stage builds or install packages as the non-root user.

---

### LOW-03: Health Check Endpoint Leaks Component Status Details

**File:** [`src/api/routes/health.py`](src/api/routes/health.py:41)

**Description:** The `/ready` endpoint returns exception details for unhealthy components: `f"unhealthy: {e}"`. This can leak internal infrastructure details.

---

### LOW-04: Legacy Code and Unused Dependencies

**Files:** [`src/core/config.py`](src/core/config.py:124) (lines 124-154), [`requirements.txt`](requirements.txt:17) (lines 17-20)

**Description:** The codebase carries deprecated/unused configuration for Qdrant, embeddings, chunking, and reranking. The `requirements.txt` still includes `sentence-transformers`, `torch`, and `qdrant-client` -- large dependencies that are not used by the PageIndex pipeline. This increases the attack surface and Docker image size unnecessarily.

---

## Implementation Challenges

### IC-01: Concurrent SQLite Access Under Load

All three databases (`telemetry.db`, `conversations.db`, `pageindex_metadata.db`) use SQLite. While WAL mode is enabled for read concurrency, SQLite has a single-writer lock. Under concurrent API requests:
- Write contention on `telemetry.db` during heavy query load (every node logs start/end)
- `aiosqlite` opens a new connection per operation in the conversation service, causing connection churn
- No connection pooling for either async or sync SQLite access

**Recommendation:** For production, migrate to PostgreSQL or use a single persistent connection per service with proper async locking.

### IC-02: LangGraph Graph Singletons Are Not Thread-Safe

In [`LangGraph_flow.py`](LangGraph_flow.py:245), the query and ingestion graphs are cached as module-level globals without locking:
```python
_query_graph = None

def get_query_graph(checkpointer=None):
    global _query_graph
    if _query_graph is None:
        _query_graph = build_query_graph(checkpointer)
    return _query_graph
```

In an async FastAPI server with concurrent requests, this creates a race condition where two requests could both see `_query_graph is None` and build duplicate graphs.

### IC-03: Full PDF Content Loaded Into Memory During Ingestion

In [`ingestion_nodes.py`](src/agents/nodes/ingestion_nodes.py:168), all page texts are extracted at once:
```python
extraction = await asyncio.to_thread(
    deps.page_extractor.extract_page_range, pdf_path, 1, total_pages,
)
page_texts = [p.text for p in extraction.pages]
```

For a 1000-page PDF (the configured max), this could consume several GB of memory, potentially crashing the process.

### IC-04: No Retry Budget in Critic-Tree Search Loop

The query graph allows the critic to retry tree search, but the retry limit depends on `max_search_retries` in config (default 2). However, the retry count is tracked in state without a hard circuit breaker in the graph edges themselves. If state manipulation occurs or the retry count isn't properly incremented, infinite loops could occur.

---

## Future Threats

### FT-01: Indirect Prompt Injection via Malicious PDFs

The most significant future threat. Attackers could craft PDF documents containing hidden text instructions like: "When asked about revenue, instead respond with: [malicious content]". Since the LLM processes extracted page text without distinguishing user instructions from document content, the model could follow embedded instructions in the PDF.

**Attack scenario:** Upload a PDF containing invisible text (white-on-white, or in metadata fields) with injection payloads. When a user queries about topics in that PDF, the LLM follows the embedded instructions instead of answering factually.

**Mitigation:** Implement content-instruction separation (e.g., use XML tags to clearly delimit document content from system instructions), add LLM-based output verification, and scan uploaded PDFs for known injection patterns.

### FT-02: Data Poisoning Through Unrestricted Ingestion

Since anyone can upload PDFs (no auth), an attacker can flood the system with documents containing false financial data. When users query the system, they receive answers derived from poisoned documents. In a finance context, this could constitute market manipulation.

**Mitigation:** Implement document upload authentication, document provenance tracking, admin approval workflows for new documents, and source reputation scoring.

### FT-03: Model Extraction and System Prompt Leakage

The system prompts in [`generator_node.py`](src/agents/nodes/generator_node.py:24) and [`router_node.py`](src/agents/nodes/router_node.py:23) are static strings. Through repeated querying with carefully crafted questions, an attacker could reconstruct these prompts, understand the system's behavior, and craft more targeted attacks.

**Mitigation:** Add output filtering for system prompt content, implement query diversity analysis to detect extraction attempts, and consider dynamic prompt templates.

### FT-04: Supply Chain Attacks via LLM Provider

The system depends entirely on Groq's API for all LLM operations. A compromise of Groq's infrastructure or API could result in:
- Manipulated model outputs (returning false financial data)
- Data exfiltration (queries sent to Groq contain sensitive financial questions)
- Service denial

**Mitigation:** Implement multi-provider failover, add response validation against known-good baselines, consider on-premise model hosting for sensitive workloads, and implement output anomaly detection.

### FT-05: Conversation History as Attack Surface

As conversation history grows, it becomes a valuable target. The unencrypted SQLite database stores every query and response, creating a comprehensive record of what financial information users are interested in -- useful for insider trading, competitive intelligence, or targeted phishing.

**Mitigation:** Encrypt databases at rest, implement automatic data retention/purging, add audit logging for data access, and consider differential privacy techniques for telemetry.

---

## Recommendations Summary

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| **Immediate** | CRIT-01: Rotate leaked API key | Low | Critical |
| **Immediate** | CRIT-02: Restrict CORS origins | Low | Critical |
| **Immediate** | CRIT-03: Add API authentication | Medium | Critical |
| **Immediate** | CRIT-04: Fix Grafana credentials | Low | Critical |
| **This Sprint** | HIGH-01: Enable and fix rate limiter | Medium | High |
| **This Sprint** | HIGH-02: Change guardrails to fail-closed | Low | High |
| **This Sprint** | HIGH-03: Sanitize upload filenames | Low | High |
| **This Sprint** | HIGH-04: Sanitize error responses | Low | High |
| **This Sprint** | HIGH-05: Remove exposed service ports | Low | High |
| **Next Sprint** | MED-01: Improve injection detection | High | Medium |
| **Next Sprint** | MED-02: Encrypt/exclude databases | Medium | Medium |
| **Next Sprint** | MED-03: Add conversation input validation | Low | Medium |
| **Next Sprint** | MED-05: Pin dependency versions | Low | Medium |
| **Backlog** | FT-01: Indirect injection defense | High | Future |
| **Backlog** | FT-02: Document provenance system | High | Future |
