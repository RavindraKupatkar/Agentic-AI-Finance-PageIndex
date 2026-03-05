"""
Tests for API Health Endpoints — src/api/routes/health.py

Covers:
    - GET /health — Basic liveness check
    - GET /ready — Readiness probe with component checks
    - GET /live — Liveness probe
    - Response format and status codes
"""

from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────
# Liveness: /health
# ──────────────────────────────────────────────────────────────


class TestHealthEndpoint:
    """Tests for the basic health check endpoint."""

    def test_health_returns_200(self, client):
        """GET /health should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status_healthy(self, client):
        """Health response should contain status=healthy."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"


# ──────────────────────────────────────────────────────────────
# Liveness: /live
# ──────────────────────────────────────────────────────────────


class TestLiveEndpoint:
    """Tests for the liveness probe."""

    def test_live_returns_200(self, client):
        """GET /live should return 200."""
        response = client.get("/live")
        assert response.status_code == 200

    def test_live_returns_alive(self, client):
        """Liveness response should indicate alive status."""
        response = client.get("/live")
        data = response.json()
        assert data["status"] == "alive"


# ──────────────────────────────────────────────────────────────
# Readiness: /ready
# ──────────────────────────────────────────────────────────────


class TestReadyEndpoint:
    """Tests for the readiness check endpoint."""

    def test_ready_returns_200(self, client):
        """GET /ready should return 200."""
        response = client.get("/ready")
        assert response.status_code == 200

    def test_ready_has_components(self, client):
        """Ready response should include component statuses."""
        response = client.get("/ready")
        data = response.json()
        assert "components" in data

    def test_ready_has_version(self, client):
        """Ready response should include version info."""
        response = client.get("/ready")
        data = response.json()
        assert "version" in data
