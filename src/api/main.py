"""
FastAPI Application Entry Point

Production-grade API for Finance Agentic RAG
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_client import make_asgi_app

from .routes import query, ingest, health, admin
from .middleware.tracing import TracingMiddleware
from ..observability.tracing import setup_tracing
from ..observability.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    setup_logging()
    setup_tracing()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="Finance Agentic RAG API",
    description="Production-grade Agentic RAG for Finance Documents",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middleware
app.add_middleware(TracingMiddleware)

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(query.router, prefix="/api/v1", tags=["Query"])
app.include_router(ingest.router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
