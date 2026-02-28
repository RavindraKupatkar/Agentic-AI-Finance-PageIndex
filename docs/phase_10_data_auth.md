# Phase 10: Convex & Clerk Integration

## Objectives
- [ ] **10a: Clerk Authentication**
  - Integrate Clerk into the Next.js frontend to replace the disabled Supabase auth.
  - Wrap the generic chat and document routes inside authenticated layouts.
  - Forward Clerk JWT tokens to the FastAPI backend for secure API access.
  
- [ ] **10b: Convex Data Layer**
  - Migrate frontend state management and database layers to Convex.
  - Create Convex schemas for `conversations`, `messages`, and `documents`.
  - Replace the current Axios-based polling for document ingestion status with Convex real-time subscriptions.
  - Ensure historical chat threads are loaded instantly via Convex queries.

- [ ] **10c: Initial UI Sync**
  - Refactor `<Sidebar>` and `<ChatInterface>` to map directly to `useQuery` hooks from Convex.
  - Implement optimistic UI updates for message sending.
