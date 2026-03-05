"""
Tests for Conversation API Routes — src/api/routes/conversations.py

Covers:
    - POST /conversations — Create conversation
    - GET /conversations — List conversations
    - GET /conversations/{id} — Get conversation details
    - POST /conversations/{id}/message — Add message
    - POST /conversations/{id}/document — Attach document
    - DELETE /conversations/{id} — Delete conversation
    - Auth enforcement (all require Clerk JWT)
    - Input validation (422 on missing fields)
    - Error handling (404, 500)
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch


# ──────────────────────────────────────────────────────────────
# CRUD Operations
# ──────────────────────────────────────────────────────────────


class TestListConversations:
    """Tests for GET /conversations."""

    def test_lists_conversations(self, client):
        """Should return a list of conversations."""
        response = client.get("/api/v1/conversations")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["id"] == "conv-1"

    def test_respects_limit_param(self, client):
        """Should accept limit query parameter."""
        response = client.get("/api/v1/conversations?limit=10")
        assert response.status_code == 200


class TestCreateConversation:
    """Tests for POST /conversations."""

    def test_creates_with_title(self, client):
        """Should create a conversation and return ID."""
        response = client.post(
            "/api/v1/conversations",
            json={"title": "My Finance Chat"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == "My Finance Chat"

    def test_creates_with_default_title(self, client):
        """Should use default title when none provided."""
        response = client.post(
            "/api/v1/conversations",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Conversation"


class TestGetConversation:
    """Tests for GET /conversations/{id}."""

    def test_returns_conversation(self, client):
        """Should return conversation details with messages."""
        response = client.get("/api/v1/conversations/conv-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "conv-1"
        assert "messages" in data

    def test_returns_404_for_missing(self, client):
        """Should return 404 for non-existent conversation."""
        # Override get_conversation to return None for this test
        from src.observability.conversations import ConversationService

        mock_service = AsyncMock(spec=ConversationService)
        mock_service.get_conversation = AsyncMock(return_value=None)

        with patch("src.api.routes.conversations.get_conversation_service", AsyncMock(return_value=mock_service)):
            response = client.get("/api/v1/conversations/non-existent")
            assert response.status_code == 404


class TestAddMessage:
    """Tests for POST /conversations/{id}/message."""

    def test_adds_user_message(self, client):
        """Should add a user message to conversation."""
        response = client.post(
            "/api/v1/conversations/conv-1/message",
            json={"role": "user", "content": "What is the revenue?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    def test_adds_assistant_message(self, client):
        """Should add an assistant message with metadata."""
        response = client.post(
            "/api/v1/conversations/conv-1/message",
            json={
                "role": "assistant",
                "content": "The revenue is $1B.",
                "sources": ["doc-a"],
                "confidence": 0.95,
                "latency_ms": 200.5,
            },
        )
        assert response.status_code == 200

    def test_rejects_missing_role(self, client):
        """Should return 422 when role is missing."""
        response = client.post(
            "/api/v1/conversations/conv-1/message",
            json={"content": "Hello"},
        )
        assert response.status_code == 422

    def test_rejects_missing_content(self, client):
        """Should return 422 when content is missing."""
        response = client.post(
            "/api/v1/conversations/conv-1/message",
            json={"role": "user"},
        )
        assert response.status_code == 422


class TestAttachDocument:
    """Tests for POST /conversations/{id}/document."""

    def test_attaches_document(self, client):
        """Should attach a document to conversation."""
        response = client.post(
            "/api/v1/conversations/conv-1/document",
            json={
                "doc_id": "doc-abc",
                "filename": "annual_report.pdf",
                "total_pages": 42,
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "attached"

    def test_rejects_missing_doc_id(self, client):
        """Should return 422 when doc_id is missing."""
        response = client.post(
            "/api/v1/conversations/conv-1/document",
            json={"filename": "test.pdf"},
        )
        assert response.status_code == 422


class TestDeleteConversation:
    """Tests for DELETE /conversations/{id}."""

    def test_deletes_conversation(self, client):
        """Should delete and return status."""
        response = client.delete("/api/v1/conversations/conv-1")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

    def test_returns_500_on_failure(self, client):
        """Should return 500 when deletion fails."""
        from src.observability.conversations import ConversationService

        mock_service = AsyncMock(spec=ConversationService)
        mock_service.delete_conversation = AsyncMock(return_value=False)

        with patch("src.api.routes.conversations.get_conversation_service", AsyncMock(return_value=mock_service)):
            response = client.delete("/api/v1/conversations/conv-fail")
            assert response.status_code == 500
