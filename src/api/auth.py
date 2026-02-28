"""
Clerk JWT Authentication for FastAPI

Verifies Clerk-issued JWTs using JWKS (JSON Web Key Sets).
Clerk signs tokens with RS256 and publishes public keys at:
    https://<clerk-domain>/.well-known/jwks.json

Modes:
    - Production: Validates JWT signature, expiry, and issuer via JWKS
    - Development: If CLERK_SECRET_KEY is not set, falls back to mock auth

Requirements:
    pip install PyJWT[crypto]
"""

import os
import time
from typing import Optional

import jwt
from jwt import PyJWKClient, PyJWKClientError
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..observability.logging import get_logger

logger = get_logger(__name__)

security = HTTPBearer(auto_error=False)

# ── JWKS Client Cache ────────────────────────────────────────
# Clerk JWKS URL is derived from the Clerk Frontend API domain.
# E.g. https://your-app.clerk.accounts.dev/.well-known/jwks.json
_jwks_client: Optional[PyJWKClient] = None
_jwks_client_initialized: bool = False


def _get_jwks_client() -> Optional[PyJWKClient]:
    """
    Lazily initialize and cache the JWKS client.

    Uses CLERK_JWKS_URL or derives it from CLERK_ISSUER_URL.
    Returns None if neither is configured (triggers mock mode).
    """
    global _jwks_client, _jwks_client_initialized

    if _jwks_client_initialized:
        return _jwks_client

    _jwks_client_initialized = True

    # Try explicit JWKS URL first
    jwks_url = os.environ.get("CLERK_JWKS_URL")

    if not jwks_url:
        # Derive from issuer URL (Clerk standard pattern)
        issuer_url = os.environ.get("CLERK_ISSUER_URL")
        if issuer_url:
            jwks_url = f"{issuer_url.rstrip('/')}/.well-known/jwks.json"

    if not jwks_url:
        # Try deriving from CLERK_SECRET_KEY presence + publishable key domain
        clerk_pk = os.environ.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "")
        if clerk_pk.startswith("pk_"):
            # Clerk publishable keys encode the frontend API domain
            # Format: pk_test_<base64-encoded-domain>
            # We can't reliably decode this, so fall back to mock
            pass

    if not jwks_url:
        logger.warning(
            "auth.no_jwks_url",
            detail="No CLERK_JWKS_URL or CLERK_ISSUER_URL set. Auth will use mock mode.",
        )
        return None

    try:
        _jwks_client = PyJWKClient(
            jwks_url,
            cache_keys=True,
            lifespan=3600,  # Cache JWKS keys for 1 hour
        )
        logger.info("auth.jwks_client_initialized", jwks_url=jwks_url)
        return _jwks_client
    except Exception as exc:
        logger.error("auth.jwks_client_init_failed", error=str(exc), jwks_url=jwks_url)
        return None


async def verify_clerk_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    """
    Verify a Clerk JWT token and return the user ID.

    Authentication flow:
        1. Extract Bearer token from Authorization header
        2. If JWKS is configured: verify JWT signature, expiry, and claims
        3. If JWKS is NOT configured: fall back to mock mode (dev only)

    Args:
        credentials: Bearer token from the Authorization header.

    Returns:
        Clerk user ID (e.g., "user_2abc123...").

    Raises:
        HTTPException(401): If the token is missing, expired, or invalid.
        HTTPException(500): If JWKS client initialization fails unexpectedly.
    """
    # ── No credentials at all ────────────────────────────
    if credentials is None or not credentials.credentials:
        # Check if we're in mock mode
        jwks = _get_jwks_client()
        if jwks is None:
            logger.debug("auth.mock_mode_no_token", detail="No token provided, mock mode active.")
            return "mock_dev_user"
        raise HTTPException(
            status_code=401,
            detail="Authorization header required. Provide a Bearer token.",
        )

    token = credentials.credentials

    # ── Try real JWKS verification ───────────────────────
    jwks = _get_jwks_client()

    if jwks is None:
        # Mock mode: CLERK_SECRET_KEY / CLERK_ISSUER_URL not set
        logger.warning(
            "auth.mock_mode",
            detail="JWKS not configured. Returning mock user. Set CLERK_ISSUER_URL for production.",
        )
        return "mock_dev_user"

    try:
        # Get the signing key from JWKS endpoint
        signing_key = jwks.get_signing_key_from_jwt(token)

        # Decode and verify the JWT
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_aud": False,  # Clerk doesn't always set audience
                "verify_iss": True,
            },
            issuer=os.environ.get("CLERK_ISSUER_URL"),
        )

        # Extract user ID — Clerk puts it in the "sub" claim
        user_id = payload.get("sub")
        if not user_id:
            logger.error("auth.missing_sub_claim", payload_keys=list(payload.keys()))
            raise HTTPException(status_code=401, detail="Token missing 'sub' claim.")

        logger.debug("auth.token_verified", user_id=user_id)
        return user_id

    except jwt.ExpiredSignatureError:
        logger.warning("auth.token_expired")
        raise HTTPException(status_code=401, detail="Token has expired. Please sign in again.")

    except jwt.InvalidIssuerError:
        logger.warning("auth.invalid_issuer")
        raise HTTPException(status_code=401, detail="Token issuer is invalid.")

    except PyJWKClientError as exc:
        logger.error("auth.jwks_fetch_failed", error=str(exc))
        raise HTTPException(
            status_code=401,
            detail="Could not verify token: JWKS key fetch failed.",
        )

    except jwt.DecodeError as exc:
        logger.warning("auth.decode_error", error=str(exc))
        raise HTTPException(status_code=401, detail="Invalid token format.")

    except jwt.InvalidTokenError as exc:
        logger.warning("auth.invalid_token", error=str(exc))
        raise HTTPException(status_code=401, detail="Token verification failed.")

    except Exception as exc:
        # Catch-all: don't leak internals
        logger.error("auth.unexpected_error", error=str(exc), error_type=type(exc).__name__)
        raise HTTPException(status_code=401, detail="Authentication failed.")
