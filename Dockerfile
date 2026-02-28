# =====================================================
# PageIndex Finance RAG — Production Dockerfile (slim)
# =====================================================
FROM python:3.12-slim

WORKDIR /app

# Install only essential system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --no-deps -r requirements.txt \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache/pip

# Copy application code
COPY src/ ./src/
COPY main.py .

# Create data directories (Render persistent disk mounts here)
RUN mkdir -p /app/data/pdfs /app/data/trees

# Create non-root user and set ownership
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port (Documentation purposes, Render dynamically assigns $PORT)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Run the application
CMD uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
