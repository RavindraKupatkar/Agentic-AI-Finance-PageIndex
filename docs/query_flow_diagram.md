# PageIndex Query E2E Flow

The diagram below shows the exact LangGraph query pipeline with all 3 routing paths, conditional edges, and retry logic.

> [!NOTE]
> Color coding: 🟢 **Green** = Simple (fast path), 🔵 **Blue** = Standard path, 🟣 **Purple** = Complex path, 🔴 **Red** = Rejection, 🟡 **Yellow** = Shared nodes

```mermaid
flowchart TD
    %% ─── Styles ────────────────────────────────
    classDef guard fill:#FF6B6B,stroke:#C0392B,color:#fff,stroke-width:2px
    classDef router fill:#F39C12,stroke:#E67E22,color:#fff,stroke-width:2px
    classDef shared fill:#F1C40F,stroke:#D4AC0F,color:#333,stroke-width:2px
    classDef simple fill:#2ECC71,stroke:#27AE60,color:#fff,stroke-width:2px
    classDef standard fill:#3498DB,stroke:#2980B9,color:#fff,stroke-width:2px
    classDef complex fill:#9B59B6,stroke:#8E44AD,color:#fff,stroke-width:2px
    classDef error fill:#E74C3C,stroke:#C0392B,color:#fff,stroke-width:2px
    classDef endpoint fill:#1ABC9C,stroke:#16A085,color:#fff,stroke-width:2px,rx:20
    classDef decision fill:#E67E22,stroke:#D35400,color:#fff,stroke-width:2px

    %% ─── Entry ─────────────────────────────────
    START(["🚀 User Query"]):::endpoint
    START --> IG

    %% ─── Input Guard ────────────────────────────
    IG["🛡️ Input Guard\n• PII detection\n• Injection blocking\n• Length validation"]:::guard
    IG -->|"✅ Valid"| RT
    IG -->|"❌ Invalid"| ERR

    ERR["⛔ Error Response\n• Blocked query\n• Safety rejection"]:::error
    ERR --> ENDR(["🔴 END\nQuery Rejected"]):::error

    %% ─── Router ─────────────────────────────────
    RT["🧭 Router\n• LLM classifies complexity\n• llama-3.1-8b-instant\n• ~200ms"]:::router
    RT -->|"🟢 Simple\nscore < 0.4"| DS_S
    RT -->|"🔵 Standard\n0.4 ≤ score < 0.7"| DS_ST
    RT -->|"🟣 Complex / Multi-hop\nscore ≥ 0.7"| PL

    %% ─── Complex Path: Planner ──────────────────
    PL["📋 Planner\n• Decomposes into sub-questions\n• llama-3.3-70b-versatile\n• ~800ms"]:::complex
    PL --> DS_C

    %% ─── Doc Selector (3 entry points) ──────────
    DS_S["📚 Doc Selector\n• Lists indexed docs from TreeStore\n• Auto-selects for single doc\n• ~9ms"]:::simple
    DS_ST["📚 Doc Selector\n• Lists indexed docs from TreeStore\n• LLM selects if multi-doc\n• ~9ms"]:::standard
    DS_C["📚 Doc Selector\n• Lists indexed docs from TreeStore\n• LLM selects if multi-doc\n• ~9ms"]:::complex

    DS_S --> TS_S
    DS_ST --> TS_ST
    DS_C --> TS_C

    %% ─── Tree Search ────────────────────────────
    TS_S["🌲 Tree Search\n• LLM reasons top-down through tree\n• Identifies relevant pages\n• gpt-oss-120b ~2800ms"]:::simple
    TS_ST["🌲 Tree Search\n• LLM reasons top-down through tree\n• Identifies relevant pages\n• gpt-oss-120b ~2800ms"]:::standard
    TS_C["🌲 Tree Search\n• LLM reasons top-down through tree\n• Identifies relevant pages\n• gpt-oss-120b ~2800ms"]:::complex

    TS_S --> PR_S
    TS_ST --> PR_ST
    TS_C --> PR_C

    %% ─── Page Retrieve ──────────────────────────
    PR_S["📑 Page Retrieve\n• Extracts text via PyMuPDF\n• Builds context string\n• ~2000ms for 25 pages"]:::simple
    PR_ST["📑 Page Retrieve\n• Extracts text via PyMuPDF\n• Builds context string\n• ~2000ms for 25 pages"]:::standard
    PR_C["📑 Page Retrieve\n• Extracts text via PyMuPDF\n• Builds context string\n• ~2000ms for 25 pages"]:::complex

    %% ─── Route After Retrieve ───────────────────
    PR_S -->|"⚡ Fast path"| FG
    PR_ST -->|"📊 Evaluate"| CR_ST
    PR_C -->|"📊 Evaluate"| CR_C

    %% ─── Critic (Standard + Complex only) ───────
    CR_ST["🔍 Critic\n• Evaluates retrieval quality\n• Checks relevance score\n• llama-3.1-8b-instant ~300ms"]:::standard
    CR_C["🔍 Critic\n• Evaluates retrieval quality\n• Checks relevance score\n• llama-3.1-8b-instant ~300ms"]:::complex

    CR_ST -->|"✅ Proceed\nrelevance ≥ threshold"| GEN_ST
    CR_ST -->|"🔄 Retry\nrelevance too low\nmax 3 retries"| TS_ST
    CR_C -->|"✅ Proceed\nrelevance ≥ threshold"| GEN_C
    CR_C -->|"🔄 Retry\nrelevance too low\nmax 3 retries"| TS_C

    %% ─── Generators ─────────────────────────────
    FG["⚡ Fast Generator\n• llama-3.1-8b-instant\n• max_tokens: 1024\n• ~230ms"]:::simple
    GEN_ST["🤖 Generator\n• llama-3.3-70b-versatile\n• max_tokens: 1024\n• ~350ms"]:::standard
    GEN_C["🤖 Generator\n• llama-3.3-70b-versatile\n• max_tokens: 1024\n• ~350ms"]:::complex

    FG --> OG_S
    GEN_ST --> OG_ST
    GEN_C --> OG_C

    %% ─── Output Guard ───────────────────────────
    OG_S["🛡️ Output Guard\n• Citation check\n• Content validation"]:::simple
    OG_ST["🛡️ Output Guard\n• Citation check\n• Content validation"]:::standard
    OG_C["🛡️ Output Guard\n• Citation check\n• Content validation"]:::complex

    OG_S --> END_S(["🟢 END\nSimple Query Complete\n~4-7s total"]):::simple
    OG_ST --> END_ST(["🔵 END\nStandard Query Complete\n~7-25s total"]):::standard
    OG_C --> END_C(["🟣 END\nComplex Query Complete\n~15-40s total"]):::complex
```

## Path Summary

| Path | Nodes | Typical Latency | LLM Calls | Use Case |
|------|-------|-----------------|-----------|----------|
| 🟢 **Simple** | input_guard → router → doc_selector → tree_search → page_retrieve → **fast_generator** → output_guard | **4–7s** | 3 (router + tree_search×2 + fast_gen) | Single-fact queries, lookups |
| 🔵 **Standard** | input_guard → router → doc_selector → tree_search → page_retrieve → **critic** → generator → output_guard | **7–25s** | 5 (router + tree×2 + critic + gen) | Analysis, summaries, comparisons |
| 🟣 **Complex** | input_guard → router → **planner** → doc_selector → tree_search → page_retrieve → **critic** → generator → output_guard | **15–40s** | 6 (router + planner + tree×2 + critic + gen) | Multi-hop reasoning, cross-doc |

## Key Differences Between Paths

| Feature | 🟢 Simple | 🔵 Standard | 🟣 Complex |
|---------|-----------|-------------|-----------|
| Planner | ❌ | ❌ | ✅ Sub-question decomposition |
| Critic | ❌ | ✅ Evaluates relevance | ✅ Evaluates relevance |
| Retry Loop | ❌ | ✅ Up to 3 retries | ✅ Up to 3 retries |
| Generator Model | `8b-instant` (fast) | `70b-versatile` (full) | `70b-versatile` (full) |
| Context Window | 2000 chars | 8000 chars | 8000 chars |
