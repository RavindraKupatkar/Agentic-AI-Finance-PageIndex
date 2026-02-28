# FinSight - Agentic Finance Document RAG
> **An Awwwards-winning enterprise platform for deep financial document analysis.**

Upload lengthy financial PDFs, interim reports, and annual reviews, and let an advanced hierarchical Agentic LangGraph engine extract, synthesize, and compare complex financial data instantly.

---

## 🚀 Features

- **Awwwards-Winning UI/UX:** Built with Next.js, Framer Motion, and Tailwind CSS. Features an immersive dark mode, orbital glowing animations, liquid mesh backgrounds, and a beautiful chat interface.
- **PageIndex Architecture:** Unlike traditional dumb chunking (Vector RAG), FinSight uses an LLM to build a hierarchical semantic tree (Table of Contents) of every document.
- **Agentic LangGraph Orchestrator:**
  - **Router:** Automatically classifies query complexity.
  - **Doc Selector:** Smartly filters which documents to search.
  - **Continuous Planner (Multi-Hop):** Breaks complex cross-document comparisons into sequential reasoning steps.
  - **Tree Searcher:** Navigates the document trees starting from the root to extract precise financial clauses.
  - **Critic:** Evaluates findings and triggers targeted re-retrieval if the answer lacks confidence.
  - **Generator:** Synthesizes the final answer with strict source citations.
- **Output Guardrails:** Automatically blocks prompt injection and appends required financial disclaimers.

---

## 📊 Architecture & Design

### 🧠 Agentic Flow
![Query Flow Diagram](docs/query_flow_diagram.png)

*The system uses LangGraph to orchestrate multiple LLM agents (Router, Planner, Critic, Generator) working together to resolve complex queries.*

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Frontend Framework** | Next.js 14 (App Router) + React 18 |
| **Frontend Styling** | Tailwind CSS + Framer Motion |
| **Backend API** | FastAPI (Python 3.11) |
| **AI Orchestration** | LangGraph + LangChain |
| **LLM Provider** | Groq (`llama-3.1-8b-instant` / `llama-3.3-70b-versatile`) |
| **Document Processing**| PyMuPDF (Text & TOC extraction) |
| **Analytics Log** | SQLite Telemetry Database |

---

## 🏁 Quick Start: Local Development

### 1. Backend Setup (FastAPI + LangGraph)

```bash
# Clone the repository and navigate to the backend
cd "Finance RAG"

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure Environment Variables
cp .env.example .env
# Edit .env and insert your GROQ_API_KEY
```

**Start the Backend Server:**
```bash
python main.py server
```
*The backend will be available at `http://localhost:8000/api/v1`*

### 2. Frontend Setup (Next.js)

```bash
# Open a new terminal and navigate to the frontend
cd "Finance RAG/finsight-frontend"

# Install dependencies
npm install

# Start the development server
npm run dev
```
*The frontend will be available at `http://localhost:3000`*

---

## 🧪 Testing

The platform includes a comprehensive, production-ready test suite designed to push the LangGraph nodes to their limits.

```bash
# Make sure the FastAPI server is running in the background first
python main.py server

# Open a new terminal and run the test suite
python test_comprehensive.py
```

**The test suite validates:**
1. **Functional Paths:** System health and tree generation.
2. **Stress Load:** Concurrent API calls and rapid-fire queries.
3. **Penetration Scenarios:** SQL Injection, prompt leaking, and massive payload rejection.
4. **RAG Evaluation Metrics (LLM-as-Judge):** Faithfulness, Relevancy, Hallucination monitoring.
5. **Guardrails:** Output validation and financial PII masking. 

*Results are automatically exported to `comprehensive_test_report.md`.*

---

## 📝 License

This project is licensed under the MIT License.
