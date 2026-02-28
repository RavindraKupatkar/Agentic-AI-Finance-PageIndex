# Phase 12: Deployment & Optimization

## Objectives
- [ ] **Backend Deployment (Render/Railway)**
  - Dockerize the FastAPI backend and LangGraph orchestrator.
  - Configure environment variables (Groq API, SQLite mount paths) in the cloud console.
  - Setup persistent volume claims for SQLite telemetry and the `data/` folder (trees and PDFs).
  
- [ ] **Frontend Deployment (Vercel)**
  - Deploy the Next.js frontend.
  - Link the Vercel project to the Render backend API URL.
  - Configure Clerk production keys and Convex production deployment URL.

- [ ] **Production Hardening**
  - Ensure CORS policies restrict access to the production frontend domain.
  - Disable raw debug logs in the terminal.
  - Implement exact rate-limiting on the API layer using `slowapi` or similar to handle public exposure gracefully without exhausting Groq tokens instantly.
