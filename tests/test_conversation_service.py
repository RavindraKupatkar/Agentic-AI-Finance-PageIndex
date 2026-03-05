"""
Tests for Conversation Service — src/observability/conversations.py

Tests the Convex proxy layer with mocked Convex service:
    - CRUD operations (create, list, get, delete)
    - Message operations (user + assistant messages)
    - Document attachment
    - Error handling (Convex failures)
    - Data mapping (Convex format → API format)
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from tests.conftest import make_conversation, make_message


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_convex_svc():
    """Provide a fresh MagicMock for the convex_service."""
    mock = MagicMock()
    mock.client = MagicMock()

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

    return mock


# ──────────────────────────────────────────────────────────────
# Create
# ──────────────────────────────────────────────────────────────


class TestCreateConversation:
    """Tests for creating conversations."""

    @pytest.mark.asyncio
    async def test_creates_with_default_title(self, mock_convex_svc):
        """Should create a conversation with 'New Conversation' default title."""
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.create_conversation()
            mock_convex_svc.create_conversation.assert_called_once_with(title="New Conversation")
            assert result == "conv-test-123"

    @pytest.mark.asyncio
    async def test_creates_with_custom_title(self, mock_convex_svc):
        """Should pass custom title to Convex."""
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            await svc.create_conversation(title="My Custom Chat")
            mock_convex_svc.create_conversation.assert_called_once_with(title="My Custom Chat")

    @pytest.mark.asyncio
    async def test_returns_empty_on_failure(self, mock_convex_svc):
        """Should return empty string on Convex failure."""
        mock_convex_svc.create_conversation.side_effect = Exception("Convex down")
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.create_conversation()
            assert result == ""


# ──────────────────────────────────────────────────────────────
# List
# ──────────────────────────────────────────────────────────────


class TestListConversations:
    """Tests for listing conversations."""

    @pytest.mark.asyncio
    async def test_maps_convex_format_to_api_format(self, mock_convex_svc):
        """Should transform Convex document format to expected API format."""
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.list_conversations()
            assert len(result) == 1
            conv = result[0]
            assert conv["id"] == "conv-1"
            assert conv["title"] == "Test Conv"
            assert "created_at" in conv
            assert "documents" in conv

    @pytest.mark.asyncio
    async def test_respects_limit(self, mock_convex_svc):
        """Should limit results to the specified count."""
        mock_convex_svc.list_conversations.return_value = [
            make_conversation(_id=f"conv-{i}") for i in range(5)
        ]
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.list_conversations(limit=3)
            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_failure(self, mock_convex_svc):
        """Should return empty list on Convex failure."""
        mock_convex_svc.list_conversations.side_effect = Exception("Convex timeout")
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.list_conversations()
            assert result == []


# ──────────────────────────────────────────────────────────────
# Get
# ──────────────────────────────────────────────────────────────


class TestGetConversation:
    """Tests for retrieving a single conversation with messages."""

    @pytest.mark.asyncio
    async def test_returns_conversation_with_messages(self, mock_convex_svc):
        """Should return conversation data with mapped messages."""
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.get_conversation("conv-1")
            assert result is not None
            assert result["id"] == "conv-1"
            assert len(result["messages"]) == 1
            assert result["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing(self, mock_convex_svc):
        """Should return None for non-existent conversation."""
        mock_convex_svc.get_conversation.return_value = None
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.get_conversation("non-existent")
            assert result is None

    @pytest.mark.asyncio
    async def test_maps_document_ids(self, mock_convex_svc):
        """Should map documentIds to documents list format."""
        mock_convex_svc.get_conversation.return_value = make_conversation(
            documentIds=["doc-a", "doc-b"]
        )
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.get_conversation("conv-1")
            assert len(result["documents"]) == 2
            assert result["documents"][0]["doc_id"] == "doc-a"

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self, mock_convex_svc):
        """Should return None on Convex failure."""
        mock_convex_svc.get_conversation.side_effect = Exception("Network error")
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.get_conversation("conv-1")
            assert result is None


# ──────────────────────────────────────────────────────────────
# Messages
# ──────────────────────────────────────────────────────────────


class TestAddMessage:
    """Tests for adding messages to conversations."""

    @pytest.mark.asyncio
    async def test_user_message_uses_send_mutation(self, mock_convex_svc):
        """User messages should use the sendMessage mutation."""
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.add_message(
                conv_id="conv-1", role="user", content="Hello world"
            )
            assert result == 1  # success indicator
            mock_convex_svc.client.mutation.assert_called_once()

    @pytest.mark.asyncio
    async def test_assistant_message_uses_save_response(self, mock_convex_svc):
        """Assistant messages should use save_agent_response."""
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.add_message(
                conv_id="conv-1",
                role="assistant",
                content="The revenue is $1M",
                sources=["doc-a"],
                confidence=0.95,
                latency_ms=150.0,
            )
            assert result == 1
            mock_convex_svc.save_agent_response.assert_called_once_with(
                conversation_id="conv-1",
                content="The revenue is $1M",
                sources=["doc-a"],
                confidence=0.95,
                latency_ms=150.0,
            )

    @pytest.mark.asyncio
    async def test_returns_negative_on_failure(self, mock_convex_svc):
        """Should return -1 on message send failure."""
        mock_convex_svc.client.mutation.side_effect = Exception("Convex error")
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.add_message(
                conv_id="conv-1", role="user", content="Hi"
            )
            assert result == -1


# ──────────────────────────────────────────────────────────────
# Document Attachment
# ──────────────────────────────────────────────────────────────


class TestAttachDocument:
    """Tests for attaching documents to conversations."""

    @pytest.mark.asyncio
    async def test_attaches_document(self, mock_convex_svc):
        """Should call Convex to attach document."""
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            await svc.attach_document(
                conv_id="conv-1",
                doc_id="doc-a",
                filename="report.pdf",
                total_pages=10,
            )
            mock_convex_svc.attach_document_to_conversation.assert_called_once_with("conv-1", "doc-a")

    @pytest.mark.asyncio
    async def test_handles_attachment_failure_silently(self, mock_convex_svc):
        """Should not raise on attachment failure."""
        mock_convex_svc.attach_document_to_conversation.side_effect = Exception("fail")
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            # Should not raise
            await svc.attach_document(
                conv_id="conv-1", doc_id="doc-a", filename="test.pdf"
            )


# ──────────────────────────────────────────────────────────────
# Delete
# ──────────────────────────────────────────────────────────────


class TestDeleteConversation:
    """Tests for deleting conversations."""

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, mock_convex_svc):
        """Should return True when deletion succeeds."""
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.delete_conversation("conv-1")
            assert result is True
            mock_convex_svc.delete_conversation.assert_called_once_with("conv-1")

    @pytest.mark.asyncio
    async def test_returns_false_on_failure(self, mock_convex_svc):
        """Should return False on Convex failure."""
        mock_convex_svc.delete_conversation.side_effect = Exception("fail")
        with patch("src.observability.conversations.convex_service", mock_convex_svc):
            from src.observability.conversations import ConversationService
            svc = ConversationService()
            result = await svc.delete_conversation("conv-1")
            assert result is False
