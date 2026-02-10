# 🚀 LangGraph RAG System

> **Production-Grade Document Q&A with SOLID Principles**

Upload PDF → Ask Questions → Get AI Answers

---

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               👤 USER INTERFACES                            │
│   🌐 Streamlit UI (Web) │ 🖥️ CLI (Command Line)           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    📥 INGESTION GRAPH                       │
│  START → extract_text → chunk_text → embed → store → END   │
│            (with real-time logging to SQLite)              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  🗄️ ChromaDB  │
                    └───────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    ❓ QUERY GRAPH                            │
│  START → embed_q → retrieve → response_generator → END     │
│                                      🤖                      │
│                            (Intelligent Agent)              │
│            (with confidence scoring & logging)             │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
capstone_project/
├── streamlit_app/
│   ├── __init__.py
│   ├── app.py                 # 🌐 Streamlit web interface
│   └── logger.py              # 📊 SQLite logging system
├── src/
│   ├── __init__.py
│   ├── config.py              # ⚙️ Centralized configuration
│   ├── main.py                # 🖥️ CLI entry point
│   ├── models/
│   │   ├── __init__.py
│   │   └── state.py           # 📊 RAGState TypedDict
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pdf_service.py     # 📄 PDF extraction
│   │   ├── embedding_service.py  # 🔢 Embeddings
│   │   ├── vector_store.py    # 🗄️ ChromaDB
│   │   ├── llm_service.py     # 🧠 Groq LLM
│   │   └── response_generator.py  # 🤖 Response Generator Agent
│   └── graphs/
│       ├── __init__.py
│       ├── nodes.py           # 🔧 Node functions
│       ├── ingestion_graph.py # 📥 Ingestion StateGraph
│       └── query_graph.py     # ❓ Query StateGraph
├── data/                      # 📂 PDF files
├── tests/                     # 🧪 Unit tests
├── docs/
│   └── ARCHITECTURE.md        # 📐 Architecture diagrams
├── .env.example
├── requirements.txt
└── README.md
```

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **UI Framework** | Streamlit (Web Interface) |
| **Graph Framework** | LangGraph (StateGraph) |
| **PDF Processing** | PyPDF |
| **Embeddings** | Sentence-Transformers (`all-MiniLM-L6-v2`) |
| **Vector Store** | ChromaDB (persistent) |
| **LLM** | Groq (`llama-3.1-70b-versatile`) |
| **Logging** | SQLite (node execution tracking) |
| **Checkpointing** | LangGraph MemorySaver |

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd capstone_project_day_02
pip install -r requirements.txt
```

### 2. Configure API Key

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 3. Run the Application

**Option A: Streamlit UI (Recommended)**
```bash
streamlit run streamlit_app/app.py
```
- 📄 Upload PDFs via drag & drop
- 💬 Interactive query interface  
- 📊 Real-time node execution logs
- 💾 SQLite-persisted metadata

**Option B: Command Line**
```bash
# Ingest a document
python main.py ingest data/document.pdf

# Ask questions
python main.py query "What is this about?"
```

### 4. Example: Streamlit UI

**Output:**
```
════════════════════════════════════════════════════════════
📁 INGESTING: data/document.pdf
════════════════════════════════════════════════════════════
  📝 Extracted 15,234 characters
  ✂️  Created 23 chunks
  🔢 Generated 23 embeddings
  💾 Stored 23 chunks in ChromaDB
════════════════════════════════════════════════════════════
✅ Ingested 23 chunks from document.pdf
```

### 4. Ask Questions

```bash
python main.py query "What is the main topic of this document?"
```

**Output:**
```
════════════════════════════════════════════════════════════
❓ QUESTION: What is the main topic of this document?
════════════════════════════════════════════════════════════
  🔢 Embedded question
  🔍 Retrieved 5 relevant chunks
  🤖 Response Generator Agent
     ├─ 🎯 Confidence: 0.80
     ├─ 📚 Sources Used: 5 chunks
     └─ ⏱️  Response Time: 2.3s
────────────────────────────────────────────────────────────
✅ ANSWER:
The main topic of this document is...
════════════════════════════════════════════════════════════
```

### 5. Check Status

```bash
python main.py status
```

## 🧱 SOLID Principles

| Principle | Implementation |
|-----------|----------------|
| **S**ingle Responsibility | Each service handles one concern |
| **O**pen/Closed | Config dataclasses, extensible services |
| **L**iskov Substitution | Swappable embedding/LLM providers |
| **I**nterface Segregation | Focused service interfaces |
| **D**ependency Inversion | Services depend on config abstraction |

## 🔄 LangGraph Graphs

### Ingestion Graph
```
START → extract_text → chunk_text → embed_chunks → store_chunks → END
```

### Query Graph (with Memory)
```
START → embed_question → retrieve_chunks → response_generator_agent → END
                                                     🤖
                                          (Intelligent Response Agent)
                                                     │
                                            [Metrics & Confidence]
                                                     │
                                              [MemorySaver]
```

## 📦 Services

| Service | Responsibility |
|---------|---------------|
| `PDFService` | Extract text from PDF, chunk text |
| `EmbeddingService` | Generate text embeddings (singleton) |
| `VectorStoreService` | ChromaDB CRUD operations (singleton) |
| `LLMService` | Low-level LLM API calls (singleton) |
| `ResponseGeneratorService` | 🤖 Intelligent response generation with metrics & confidence |

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_services.py -v
```

## 📚 Python API

```python
from src.graphs import ingest_pdf, ask_question

# Ingest a document
result = ingest_pdf("data/report.pdf")
print(result)  # ✅ Ingested 45 chunks from report.pdf

# Ask questions with conversation memory
answer = ask_question(
    "What are the key findings?",
    thread_id="session_001"
)
print(answer)
```

## ⚙️ Configuration

All settings in `src/config.py`:

```python
# Chunking
CHUNK_SIZE = 800
CHUNK_OVERLAP = 200

# Embeddings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Retrieval
TOP_K = 5

# LLM
LLM_MODEL = "llama-3.1-70b-versatile"
TEMPERATURE = 0.3
```

## 📐 Architecture Diagrams

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for detailed Mermaid diagrams including:
- System Overview
- Ingestion Graph Flow
- Query Graph Flow
- Data Flow Sequence
- SOLID Principles Mindmap

---

**Built for ADCET Agentic AI Workshop - Day 2 Capstone Project**

*Framework: LangGraph | LLM: Groq | Vector Store: ChromaDB*
