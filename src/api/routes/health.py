"""
Health Check Routes — Liveness / Readiness probes

Compatible with Render, Kubernetes, and Docker HEALTHCHECK.
"""

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict

router = APIRouter()

# Project root: 4 levels up from src/api/routes/health.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class HealthResponse(BaseModel):
    status: str
    version: str
    components: Dict[str, str]


@router.get("/health")
async def health_check():
    """Basic health check — used by Render & Docker HEALTHCHECK."""
    return {"status": "healthy"}


@router.get("/ready", response_model=HealthResponse)
async def readiness_check():
    """
    Readiness probe — verifies PageIndex components are operational.

    Checks:
    - data/trees directory exists (tree store accessible)
    - Groq LLM client can be instantiated
    """
    components: Dict[str, str] = {}

    # Check tree store directory
    trees_dir = _PROJECT_ROOT / "data" / "trees"
    if trees_dir.is_dir():
        tree_count = len(list(trees_dir.glob("*.json")))
        components["tree_store"] = f"healthy ({tree_count} trees)"
    else:
        components["tree_store"] = "degraded: data/trees/ not found"

    # Check LLM client
    try:
        from ...llm.groq_client import GroqClient

        GroqClient()
        components["llm"] = "healthy"
    except Exception as e:
        components["llm"] = f"unhealthy: {e}"

    all_healthy = all("healthy" in v for v in components.values())

    return HealthResponse(
        status="ready" if all_healthy else "degraded",
        version="1.0.0",
        components=components,
    )


@router.get("/live")
async def liveness_check():
    """Liveness probe."""
    return {"status": "alive"}
