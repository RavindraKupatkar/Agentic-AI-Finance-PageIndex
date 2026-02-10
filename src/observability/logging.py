"""
Structured Logging - JSON logging with structlog

Provides structured, queryable logs for production.
"""

import structlog
import logging
import sys

from ..core.config import settings


def setup_logging():
    """
    Configure structured logging.
    
    Uses JSON format in production, colored output in development.
    """
    # Configure structlog processors
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if settings.environment == "production":
        # JSON output for production
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ]
    else:
        # Colored output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper())
    )


def get_logger(name: str = None):
    """Get a structlog logger"""
    return structlog.get_logger(name or __name__)


# Create default logger
logger = get_logger("finance_rag")
