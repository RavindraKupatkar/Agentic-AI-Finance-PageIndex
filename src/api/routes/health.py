"""
Health Check Routes - Kubernetes liveness/readiness probes
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    components: Dict[str, str]


@router.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy"}


@router.get("/ready", response_model=HealthResponse)
async def readiness_check():
    """
    Kubernetes readiness probe
    Checks all dependencies are available
    """
    from ...vectorstore.qdrant_store import QdrantStore
    from ...llm.groq_client import GroqClient
    
    components = {}
    
    # Check vector store
    try:
        store = QdrantStore()
        store.health_check()
        components["vectorstore"] = "healthy"
    except Exception as e:
        components["vectorstore"] = f"unhealthy: {e}"
    
    # Check LLM
    try:
        llm = GroqClient()
        llm.health_check()
        components["llm"] = "healthy"
    except Exception as e:
        components["llm"] = f"unhealthy: {e}"
    
    all_healthy = all(v == "healthy" for v in components.values())
    
    return HealthResponse(
        status="ready" if all_healthy else "degraded",
        version="1.0.0",
        components=components
    )


@router.get("/live")
async def liveness_check():
    """Kubernetes liveness probe"""
    return {"status": "alive"}
