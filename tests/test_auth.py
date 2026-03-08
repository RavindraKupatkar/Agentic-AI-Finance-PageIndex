"""
Tests for Clerk JWT Authentication — src/api/auth.py

Covers:
    - Mock mode behavior (no JWKS configured)
    - Missing credentials
    - Token extraction
    - JWKS client initialization edge cases
    - Expired / malformed / invalid token handling
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import src.api.auth as auth_module


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _reset_jwks_cache():
    """Reset the module-level JWKS client cache between tests."""
    auth_module._jwks_client = None
    auth_module._jwks_client_initialized = False


@pytest.fixture(autouse=True)
def reset_jwks():
    """Reset JWKS state before each test."""
    _reset_jwks_cache()
    yield
    _reset_jwks_cache()


# ──────────────────────────────────────────────────────────────
# JWKS Client Initialization
# ──────────────────────────────────────────────────────────────


class TestJWKSClientInit:
    """Tests for _get_jwks_client initialization logic."""

    def test_returns_none_when_no_clerk_env_vars(self, monkeypatch):
        """JWKS client should be None when no Clerk vars are set (mock mode)."""
        monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
        monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
        monkeypatch.delenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", raising=False)

        result = auth_module._get_jwks_client()
        assert result is None

    def test_derives_jwks_url_from_issuer(self, monkeypatch):
        """Should derive JWKS URL from CLERK_ISSUER_URL when CLERK_JWKS_URL is not set."""
        monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
        monkeypatch.setenv("CLERK_ISSUER_URL", "https://my-app.clerk.accounts.dev")

        with patch("src.api.auth.PyJWKClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            result = auth_module._get_jwks_client()

            mock_cls.assert_called_once()
            call_args = mock_cls.call_args
            assert "my-app.clerk.accounts.dev/.well-known/jwks.json" in call_args[0][0]
            assert result is not None

    def test_uses_explicit_jwks_url(self, monkeypatch):
        """Should use CLERK_JWKS_URL directly when provided."""
        monkeypatch.setenv("CLERK_JWKS_URL", "https://custom.jwks/keys")

        with patch("src.api.auth.PyJWKClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            result = auth_module._get_jwks_client()

            mock_cls.assert_called_once_with(
                "https://custom.jwks/keys",
                cache_keys=True,
                lifespan=3600,
            )
            assert result is not None

    def test_caches_jwks_client(self, monkeypatch):
        """Should only initialize the JWKS client once (singleton)."""
        monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks")

        with patch("src.api.auth.PyJWKClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            first = auth_module._get_jwks_client()
            second = auth_module._get_jwks_client()

            assert first is second
            mock_cls.assert_called_once()

    def test_handles_jwks_init_failure(self, monkeypatch):
        """Should return None if PyJWKClient initialization raises."""
        monkeypatch.setenv("CLERK_JWKS_URL", "https://bad.url/jwks")

        with patch("src.api.auth.PyJWKClient", side_effect=Exception("Network error")):
            result = auth_module._get_jwks_client()
            assert result is None


# ──────────────────────────────────────────────────────────────
# Token Verification
# ──────────────────────────────────────────────────────────────


class TestVerifyClerkToken:
    """Tests for verify_clerk_token dependency."""

    @pytest.mark.asyncio
    async def test_mock_mode_no_credentials(self, monkeypatch):
        """In mock mode (no JWKS), missing credentials should return mock user."""
        monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
        monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
        monkeypatch.delenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", raising=False)

        result = await auth_module.verify_clerk_token(credentials=None)
        assert result == "mock_dev_user"

    @pytest.mark.asyncio
    async def test_mock_mode_with_token(self, monkeypatch):
        """In mock mode, even with a token, should return mock user (no JWKS to verify)."""
        monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
        monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="some-token")
        result = await auth_module.verify_clerk_token(credentials=creds)
        assert result == "mock_dev_user"

    @pytest.mark.asyncio
    async def test_missing_credentials_production_mode(self, monkeypatch):
        """In production mode (JWKS configured), missing credentials should raise 401."""
        monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks")

        with patch("src.api.auth.PyJWKClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            # Force re-init
            _reset_jwks_cache()

            with pytest.raises(HTTPException) as exc_info:
                await auth_module.verify_clerk_token(credentials=None)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_token_string(self, monkeypatch):
        """Empty token string should be treated as missing credentials."""
        monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks")

        with patch("src.api.auth.PyJWKClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            _reset_jwks_cache()

            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
            with pytest.raises(HTTPException) as exc_info:
                await auth_module.verify_clerk_token(credentials=creds)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_returns_user_id(self, monkeypatch):
        """Valid JWT should return the 'sub' claim as user ID."""
        monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks")
        monkeypatch.setenv("CLERK_ISSUER_URL", "https://test.clerk.accounts.dev")

        mock_jwks = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-public-key"
        mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch("src.api.auth.PyJWKClient", return_value=mock_jwks):
            _reset_jwks_cache()

            with patch("src.api.auth.jwt.decode") as mock_decode:
                mock_decode.return_value = {"sub": "user_2abc123", "iss": "https://test.clerk.accounts.dev"}

                creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid.jwt.token")
                result = await auth_module.verify_clerk_token(credentials=creds)

                assert result == "user_2abc123"

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self, monkeypatch):
        """Expired JWT should raise 401."""
        import jwt as pyjwt
        monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks")

        mock_jwks = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch("src.api.auth.PyJWKClient", return_value=mock_jwks):
            _reset_jwks_cache()

            with patch("src.api.auth.jwt.decode", side_effect=pyjwt.ExpiredSignatureError()):
                creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="expired.jwt.token")
                with pytest.raises(HTTPException) as exc_info:
                    await auth_module.verify_clerk_token(credentials=creds)
                assert exc_info.value.status_code == 401
                assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_issuer_raises_401(self, monkeypatch):
        """Token with wrong issuer should raise 401."""
        import jwt as pyjwt
        monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks")

        mock_jwks = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch("src.api.auth.PyJWKClient", return_value=mock_jwks):
            _reset_jwks_cache()

            with patch("src.api.auth.jwt.decode", side_effect=pyjwt.InvalidIssuerError()):
                creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-issuer.jwt")
                with pytest.raises(HTTPException) as exc_info:
                    await auth_module.verify_clerk_token(credentials=creds)
                assert exc_info.value.status_code == 401
                assert "issuer" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_malformed_token_raises_401(self, monkeypatch):
        """Malformed JWT should raise 401."""
        import jwt as pyjwt
        monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks")

        mock_jwks = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch("src.api.auth.PyJWKClient", return_value=mock_jwks):
            _reset_jwks_cache()

            with patch("src.api.auth.jwt.decode", side_effect=pyjwt.DecodeError("bad token")):
                creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not.a.jwt")
                with pytest.raises(HTTPException) as exc_info:
                    await auth_module.verify_clerk_token(credentials=creds)
                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_sub_claim_raises_401(self, monkeypatch):
        """JWT without 'sub' claim should raise 401."""
        monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks")

        mock_jwks = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch("src.api.auth.PyJWKClient", return_value=mock_jwks):
            _reset_jwks_cache()

            with patch("src.api.auth.jwt.decode", return_value={"iss": "test", "exp": 9999999999}):
                creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="no-sub.jwt")
                with pytest.raises(HTTPException) as exc_info:
                    await auth_module.verify_clerk_token(credentials=creds)
                assert exc_info.value.status_code == 401
                # The 'sub' error may be caught by the generic handler
                assert exc_info.value.detail  # Must have an error message
