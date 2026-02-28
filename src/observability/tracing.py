"""
OpenTelemetry Tracing - Distributed tracing setup

Traces requests through the entire RAG pipeline.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

from ..core.config import settings


# Global tracer
tracer = trace.get_tracer(__name__)


def setup_tracing():
    """
    Configure OpenTelemetry tracing.
    
    Exports traces to OTLP endpoint (Tempo, Jaeger, etc.)
    """
    resource = Resource.create({
        "service.name": settings.service_name,
        "service.version": "1.0.0",
        "deployment.environment": settings.environment
    })
    
    provider = TracerProvider(resource=resource)
    
    # Configure OTLP exporter if endpoint provided (lazy import to avoid grpcio dep)
    if settings.otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            otlp_exporter = OTLPSpanExporter(
                endpoint=settings.otlp_endpoint,
                insecure=True
            )
            processor = BatchSpanProcessor(otlp_exporter)
            provider.add_span_processor(processor)
        except ImportError:
            import logging
            logging.getLogger(__name__).warning(
                "opentelemetry-exporter-otlp not installed; tracing export disabled"
            )
    
    trace.set_tracer_provider(provider)
    
    # Update global tracer
    global tracer
    tracer = trace.get_tracer(__name__)


def get_tracer(name: str = None):
    """Get a tracer instance"""
    return trace.get_tracer(name or __name__)
