"""
Tests for Backend Configuration — src/core/config.py

Covers:
    - Default values for all settings
    - Environment variable loading
    - Port configuration
    - CORS origins parsing
    - PageIndex settings validation
"""

from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────
# Settings Defaults
# ──────────────────────────────────────────────────────────────


class TestSettingsDefaults:
    """Tests for default configuration values."""

    def test_default_environment_is_development(self, monkeypatch):
        """Default ENV should be 'development'."""
        monkeypatch.delenv("ENV", raising=False)
        from src.core.config import Settings
        s = Settings()
        assert s.environment == "development"

    def test_api_port_default(self, monkeypatch):
        """Default API port should be 8080."""
        monkeypatch.delenv("PORT", raising=False)
        monkeypatch.delenv("API_PORT", raising=False)
        from src.core.config import Settings
        s = Settings()
        assert s.api_port == 8080

    def test_api_port_from_env(self, monkeypatch):
        """PORT env var should override default API port."""
        monkeypatch.setenv("PORT", "9090")
        from src.core.config import Settings
        s = Settings()
        assert s.api_port == 9090

    def test_api_host_default(self, monkeypatch):
        """Default API host should be 0.0.0.0."""
        monkeypatch.delenv("API_HOST", raising=False)
        from src.core.config import Settings
        s = Settings()
        assert s.api_host == "0.0.0.0"

    def test_convex_url_from_env(self, monkeypatch):
        """CONVEX_URL should be loaded from environment."""
        monkeypatch.setenv("CONVEX_URL", "https://my-project.convex.cloud")
        from src.core.config import Settings
        s = Settings()
        assert s.convex_url == "https://my-project.convex.cloud"

    def test_service_name_default(self):
        """Service name should have a default value."""
        from src.core.config import Settings
        s = Settings()
        assert s.service_name == "finance-agentic-rag"


# ──────────────────────────────────────────────────────────────
# CORS Configuration
# ──────────────────────────────────────────────────────────────


class TestCORSConfig:
    """Tests for CORS origins parsing."""

    def test_default_cors_includes_localhost(self, monkeypatch):
        """Default CORS should include localhost:3000."""
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
        from src.core.config import Settings
        s = Settings()
        assert "http://localhost:3000" in s.allowed_origins

    def test_comma_separated_cors(self, monkeypatch):
        """ALLOWED_ORIGINS should parse comma-separated origins."""
        monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.com,https://admin.com")
        from src.core.config import Settings
        s = Settings()
        assert "https://app.com" in s.allowed_origins
        assert "https://admin.com" in s.allowed_origins


# ──────────────────────────────────────────────────────────────
# PageIndex Settings
# ──────────────────────────────────────────────────────────────


class TestPageIndexSettings:
    """Tests for PageIndex-specific configuration."""

    def test_default_llm_model(self):
        """Default LLM model should be set."""
        from src.core.config import Settings
        s = Settings()
        assert s.default_llm_model is not None
        assert len(s.default_llm_model) > 0

    def test_default_max_pdf_pages_is_positive(self):
        """Default max PDF pages should be positive."""
        from src.core.config import Settings
        s = Settings()
        assert s.max_pdf_pages > 0

    def test_pdfs_dir_has_default(self):
        """PDFs directory should have a default path."""
        from src.core.config import Settings
        s = Settings()
        assert s.pdfs_dir is not None
        assert len(s.pdfs_dir) > 0

    def test_max_query_length_is_reasonable(self):
        """Max query length should be within a reasonable range."""
        from src.core.config import Settings
        s = Settings()
        assert 100 <= s.max_query_length <= 10000

    def test_max_tree_depth_bounds(self):
        """Tree depth should be bounded between 2 and 10."""
        from src.core.config import Settings
        s = Settings()
        assert 2 <= s.max_tree_depth <= 10

    def test_max_retries_default(self):
        """Max retries should have a sensible default."""
        from src.core.config import Settings
        s = Settings()
        assert s.max_retries >= 1
