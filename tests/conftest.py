"""
Shared Fixtures — FinSight Test Suite

Provides reusable pytest fixtures for:
    - FastAPI TestClient with mocked auth
    - Mock Convex service
    - Factory functions for test data
    - Monkeypatched environment variables
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock

# ──────────────────────────────────────────────────────────────
# CRITICAL: Mock the 'convex' package before any project imports.
# The convex Python SDK is not installed locally (production dep).
# This prevents ModuleNotFoundError cascading through the import chain.
# ──────────────────────────────────────────────────────────────

_mock_convex_module = MagicMock()
sys.modules.setdefault("convex", _mock_convex_module)
sys.modules.setdefault("convex.client", _mock_convex_module)

import pytest
from unittest.mock import AsyncMock, patch

# ──────────────────────────────────────────────────────────────
# Environment: patch BEFORE any project imports
# ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _patch_env(monkeypatch):
    """Ensure tests run with known env vars and no real service connections."""
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://test.clerk.accounts.dev")
    monkeypatch.setenv("CLERK_JWKS_URL", "https://test.clerk.accounts.dev/.well-known/jwks.json")
    monkeypatch.setenv("CONVEX_URL", "https://test.convex.cloud")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000")


# ──────────────────────────────────────────────────────────────
# Mock: Convex Service
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def mock_convex():
    """Provide a MagicMock replacing the convex_service singleton."""
    mock = MagicMock()
    mock.client = MagicMock()

    # Sensible defaults
    mock.create_conversation.return_value = "conv-test-123"
    mock.list_conversations.return_value = [
        {
            "_id": "conv-1",
            "title": "Test Conv",
            "createdAt": 1700000000,
            "updatedAt": 1700000000,
            "documentIds": ["doc-a"],
        }
    ]
    mock.get_conversation.return_value = {
        "_id": "conv-1",
        "title": "Test Conv",
        "createdAt": 1700000000,
        "updatedAt": 1700000000,
        "documentIds": ["doc-a"],
    }
    mock.get_conversation_messages.return_value = [
        {
            "_id": "msg-1",
            "role": "user",
            "content": "Hello",
            "createdAt": 1700000000,
        }
    ]
    mock.delete_conversation.return_value = None
    mock.attach_document_to_conversation.return_value = None
    mock.save_agent_response.return_value = "msg-resp-1"
    mock.list_documents.return_value = []

    return mock


# ──────────────────────────────────────────────────────────────
# Mock: Auth (bypass Clerk JWT verification)
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def mock_auth():
    """Patch verify_clerk_token to return a mock user ID."""
    with patch("src.api.auth.verify_clerk_token", return_value="test-user-123") as m:
        yield m


# ──────────────────────────────────────────────────────────────
# FastAPI TestClient
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def client(mock_convex):
    """
    Provide a FastAPI TestClient with mocked auth and Convex.

    Uses FastAPI dependency_overrides to bypass Clerk JWT auth,
    and patches the convex_service module-level variable.
    """
    from src.api.auth import verify_clerk_token
    from src.api.main import app
    from src.observability.conversations import ConversationService

    # Override FastAPI's Depends(verify_clerk_token) → always return test user
    async def _mock_verify():
        return "test-user-123"

    app.dependency_overrides[verify_clerk_token] = _mock_verify

    # Mock the ConversationService singleton that routes use
    mock_service = MagicMock(spec=ConversationService)
    mock_service.create_conversation = AsyncMock(return_value="conv-test-123")
    mock_service.list_conversations = AsyncMock(return_value=[
        {"id": "conv-1", "title": "Test Conv", "created_at": 1700000000, "documents": []}
    ])
    mock_service.get_conversation = AsyncMock(return_value={
        "id": "conv-1", "title": "Test Conv", "messages": [
            {"id": "msg-1", "role": "user", "content": "Hello"}
        ], "documents": []
    })
    mock_service.add_message = AsyncMock(return_value=1)
    mock_service.attach_document = AsyncMock(return_value=None)
    mock_service.delete_conversation = AsyncMock(return_value=True)

    with patch("src.api.routes.conversations.get_conversation_service", AsyncMock(return_value=mock_service)):
        from fastapi.testclient import TestClient
        yield TestClient(app)

    # Clean up overrides
    app.dependency_overrides.clear()


# ──────────────────────────────────────────────────────────────
# Factory Functions
# ──────────────────────────────────────────────────────────────

def make_query_request(**overrides) -> dict:
    """Factory for PageIndex query request payloads."""
    defaults = {
        "question": "What is the total revenue?",
        "thread_id": "default",
        "top_k": 5,
    }
    defaults.update(overrides)
    return defaults


def make_conversation(**overrides) -> dict:
    """Factory for conversation test data."""
    defaults = {
        "_id": "conv-factory-1",
        "title": "Factory Conversation",
        "createdAt": 1700000000,
        "updatedAt": 1700000000,
        "documentIds": [],
    }
    defaults.update(overrides)
    return defaults


def make_message(**overrides) -> dict:
    """Factory for message test data."""
    defaults = {
        "_id": "msg-factory-1",
        "role": "user",
        "content": "Test message content",
        "createdAt": 1700000000,
    }
    defaults.update(overrides)
    return defaults
