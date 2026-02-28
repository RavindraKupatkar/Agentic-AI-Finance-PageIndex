# React Frontend Implementation Plan — PageIndex Finance RAG

## Overview

Build a premium, dark-themed React frontend for the PageIndex Finance RAG system.
Connects to the existing FastAPI backend at `http://127.0.0.1:8000`.

### Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Framework | **React 19 + Vite** | Fast dev server, no SSR needed |
| Styling | **Vanilla CSS** (custom design system) | Full control, no utility bloat |
| Animations | **Framer Motion** | Smooth page transitions, micro-interactions |
| HTTP | **Axios** | Interceptors, SSE support |
| Routing | **React Router v7** | Client-side SPA routing |
| Icons | **Lucide React** | Lightweight, consistent icon set |
| Markdown | **react-markdown + rehype** | Render LLM answers with formatting |
| State | **React Context + useReducer** | Simple, no Redux needed |

### Design Direction

- **Dark-first** theme with optional light mode
- **Glassmorphism** — frosted glass cards, backdrop blur
- **Color palette**: Electric Blue (`#3B82F6`) + Emerald (`#10B981`) accents on deep navy (`#0F172A`)
- **Typography**: Inter (headings) + JetBrains Mono (code/sources)
- **Micro-animations**: hover lifts, skeleton loaders, typing indicators

---

## API Endpoints (Backend)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/v1/pageindex/query` | Ask a question |
| `POST` | `/api/v1/pageindex/ingest` | Upload PDF |
| `GET` | `/api/v1/pageindex/documents` | List indexed docs |
| `GET` | `/api/v1/pageindex/query/{id}` | Query telemetry detail |
| `GET` | `/api/v1/pageindex/telemetry` | Recent query logs |
| `GET` | `/api/v1/pageindex/health` | Health check |
| `GET` | `/api/v1/admin/status` | System status |
| `GET` | `/api/v1/admin/telemetry/dashboard` | Full telemetry dashboard |

---

## Pages & Components

### Page 1: Chat (`/`)

The primary interface — a conversational Q&A experience.

**Components:**
- `ChatWindow` — scrollable message list with auto-scroll
- `MessageBubble` — user (right, blue) and assistant (left, glass) bubbles
- `SourceCard` — expandable citation cards showing `filename p.X`
- `ConfidenceBadge` — color-coded badge (green ≥0.7, yellow ≥0.4, red <0.4)
- `QueryTypeTag` — pill showing simple/standard/complex
- `TypingIndicator` — animated dots while waiting for response
- `ChatInput` — auto-resizing textarea with send button + keyboard shortcut

**Behavior:**
- Submit question → show typing indicator → display streamed answer
- Show sources as clickable cards below the answer
- Display confidence score and query type
- Persist chat history in localStorage per thread_id

---

### Page 2: Documents (`/documents`)

PDF upload and document management.

**Components:**
- `UploadZone` — drag-and-drop area with progress bar
- `DocumentCard` — glass card showing doc info (title, pages, tree depth)
- `DocumentGrid` — responsive grid of indexed documents
- `UploadProgress` — step indicator: uploading → extracting → building tree → storing
- `EmptyState` — illustration + CTA when no docs are indexed

**Behavior:**
- Drag-and-drop or click to upload PDF
- Show ingestion progress with live step indicators
- Display all indexed documents from `/documents` endpoint
- Click document card to see tree structure (future)

---

### Page 3: Admin Dashboard (`/admin`)

Telemetry, system health, and query analytics.

**Components:**
- `StatsGrid` — 4 metric cards (queries, nodes, LLM calls, errors)
- `QueryLogTable` — sortable table of recent queries
- `LatencyChart` — bar chart of query latency distribution
- `ErrorList` — recent errors with expandable stack traces
- `HealthIndicator` — system component status (telemetry, Groq, docs)
- `NodeTimeline` — visual timeline of node executions for a query

**Behavior:**
- Auto-refresh every 30s
- Click query row → expand to show node executions + LLM calls
- Color-coded error severity
- Export telemetry as CSV (client-side)

---

## 6-Phase Implementation Plan

### Phase 1: Project Setup & Design System
**Estimated time: 2-3 hours**

1. Initialize Vite + React project in `frontend/` directory
2. Install dependencies (framer-motion, axios, react-router, lucide-react, react-markdown)
3. Create CSS design system:
   - `variables.css` — colors, spacing, typography, shadows, glass effects
   - `reset.css` — normalize + base styles
   - `animations.css` — keyframes for common animations
4. Create layout components: `AppShell`, `Sidebar`, `Header`, `PageContainer`
5. Set up React Router with 3 routes
6. Configure Axios with base URL and interceptors
7. Create `api/` service layer with typed functions for each endpoint

### Phase 2: Chat Page (Core)
**Estimated time: 3-4 hours**

1. Build `ChatWindow` with message list and auto-scroll
2. Build `ChatInput` with auto-resize and Shift+Enter support
3. Build `MessageBubble` with markdown rendering
4. Wire up `POST /pageindex/query` via Axios
5. Add `TypingIndicator` animation during loading
6. Add `SourceCard` with citations
7. Add `ConfidenceBadge` and `QueryTypeTag`
8. Add thread management (new chat, clear history)

### Phase 3: Documents Page
**Estimated time: 2-3 hours**

1. Build `UploadZone` with drag-and-drop + file input
2. Build `UploadProgress` with step animation
3. Wire up `POST /pageindex/ingest` with progress tracking
4. Build `DocumentCard` with glassmorphism styling
5. Build `DocumentGrid` with responsive layout
6. Wire up `GET /pageindex/documents` for listing
7. Add empty state for zero documents

### Phase 4: Admin Dashboard
**Estimated time: 2-3 hours**

1. Build `StatsGrid` showing table counts
2. Build `QueryLogTable` with sortable columns
3. Wire up `GET /admin/telemetry/dashboard` and `/pageindex/telemetry`
4. Build `ErrorList` with expandable details
5. Build `HealthIndicator` from `/pageindex/health`
6. Add auto-refresh (30s interval)
7. Add CSV export functionality

### Phase 5: Polish & Animations
**Estimated time: 1-2 hours**

1. Add Framer Motion page transitions
2. Add hover/focus micro-animations on all interactive elements
3. Add skeleton loaders for every loading state
4. Add toast notifications for errors and success
5. Responsive design pass (mobile → tablet → desktop)
6. Light mode toggle (optional)

### Phase 6: Integration Testing & Deployment
**Estimated time: 1-2 hours**

1. Test all 3 pages against live backend
2. Fix any CORS or API integration issues
3. Add error boundary components
4. Update `docker-compose.yml` for frontend service
5. Update `README.md` with frontend instructions
6. Build production bundle and verify

---

## File Structure

```
frontend/
├── index.html
├── vite.config.js
├── package.json
├── public/
│   └── favicon.svg
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── api/
    │   └── client.js          # Axios instance + API functions
    ├── styles/
    │   ├── variables.css      # Design tokens
    │   ├── reset.css          # Normalize + base
    │   ├── animations.css     # Keyframes
    │   └── components/        # Per-component CSS
    ├── components/
    │   ├── layout/
    │   │   ├── AppShell.jsx
    │   │   ├── Sidebar.jsx
    │   │   └── Header.jsx
    │   ├── chat/
    │   │   ├── ChatWindow.jsx
    │   │   ├── ChatInput.jsx
    │   │   ├── MessageBubble.jsx
    │   │   ├── SourceCard.jsx
    │   │   ├── ConfidenceBadge.jsx
    │   │   └── TypingIndicator.jsx
    │   ├── documents/
    │   │   ├── UploadZone.jsx
    │   │   ├── UploadProgress.jsx
    │   │   ├── DocumentCard.jsx
    │   │   └── DocumentGrid.jsx
    │   └── admin/
    │       ├── StatsGrid.jsx
    │       ├── QueryLogTable.jsx
    │       ├── ErrorList.jsx
    │       └── HealthIndicator.jsx
    ├── pages/
    │   ├── ChatPage.jsx
    │   ├── DocumentsPage.jsx
    │   └── AdminPage.jsx
    └── context/
        └── AppContext.jsx     # Global state
```

---

## Verification Plan

### Manual Testing
- Upload a PDF → verify ingestion completes → see it in Documents page
- Ask a question → verify answer appears with sources and confidence
- Check Admin dashboard → verify all 4 table counts are visible
- Test responsive layout on mobile viewport

### Automated
- `npm run build` — ensure production bundle compiles
- Verify CORS works from `localhost:5173` → `localhost:8000`
