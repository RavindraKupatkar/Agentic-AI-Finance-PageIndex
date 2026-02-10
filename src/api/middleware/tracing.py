"""
Tracing Middleware - OpenTelemetry integration for FastAPI
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time
import uuid

from ...observability.tracing import tracer


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware to add OpenTelemetry tracing to all requests"""
    
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        
        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}"
        ) as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("request.id", request_id)
            
            start_time = time.time()
            
            # Add request ID to state for downstream use
            request.state.request_id = request_id
            
            response = await call_next(request)
            
            # Record response info
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.latency_ms", (time.time() - start_time) * 1000)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
