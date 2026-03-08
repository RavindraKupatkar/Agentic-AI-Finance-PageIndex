"""
FastAPI Application Entry Point

Production-grade API for Finance Agentic RAG
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_client import make_asgi_app

from .routes import health
from .routes.pageindex import router as pageindex_router
from .routes.conversations import router as conversations_router
from .middleware.tracing import TracingMiddleware
from ..observability.tracing import setup_tracing
from ..observability.logging import setup_logging
from ..core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    setup_logging()
    setup_tracing()
    # Initialize telemetry DB on startup
    from ..observability.telemetry import get_telemetry_service
    await get_telemetry_service()
    from ..observability.conversations import get_conversation_service
    await get_conversation_service()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="FinSight API",
    description="AI-Powered Finance Document Intelligence by SyncroAI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware — explicit origins + Vercel preview wildcard
# Set ALLOWED_ORIGINS env var in production (comma-separated)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middleware
app.add_middleware(TracingMiddleware)

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

app.include_router(health.router, tags=["Health"])
app.include_router(pageindex_router, prefix="/api/v1", tags=["PageIndex"])
app.include_router(conversations_router, prefix="/api/v1", tags=["Conversations"])
