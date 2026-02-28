# =====================================================
# PageIndex Finance RAG — Production Dockerfile (slim)
# =====================================================
# Canonical copy lives in deploy/Dockerfile — keep in sync.
# This root-level copy exists so `gcloud builds submit --tag`
# finds it without needing -f deploy/Dockerfile.
# =====================================================
FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck + clean up in same layer
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (single pass, no cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY main.py .
COPY LangGraph_flow.py .

# Create data directories & non-root user
RUN mkdir -p /app/data/pdfs /app/data/trees \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Cloud Run injects PORT (default 8080). Give the process time to start.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

CMD uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8080}
