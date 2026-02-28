"""
Convex Service Wrapper

Stateless database and storage management using the Convex cloud backend.
Replaces all local SQLite and physical file storage operations.
"""
from convex import ConvexClient
from src.core.config import settings

class ConvexService:
    def __init__(self):
        # We do not use set_auth for the backend because these mutations 
        # are open to internal admin functions or authenticated via passed args
        self.client = ConvexClient(settings.convex_url)

    # ─────────────────────────────────────────────
    # Trees
    # ─────────────────────────────────────────────

    def save_tree(self, document_id: str, structure: dict) -> str:
        """Saves a generated PageIndex JSON tree to Convex."""
        return self.client.mutation("trees:saveTree", {
            "documentId": document_id,
            "structure": structure
        })

    def get_tree(self, document_id: str) -> dict:
        """Retrieves a PageIndex JSON tree from Convex."""
        result = self.client.query("trees:getTree", {
            "documentId": document_id
        })
        if not result:
            raise ValueError(f"Tree structure for document {document_id} not found in Convex.")
        return result.get("structure")

    # ─────────────────────────────────────────────
    # Documents & Storage
    # ─────────────────────────────────────────────

    def list_documents(self, clerk_id: str):
        """Gets all documents for a given user."""
        return self.client.query("documents:listDocuments", {
            "clerkId": clerk_id
        })

    def update_document_status(self, document_id: str, status: str, **kwargs):
        """Updates the ingestion status of a document."""
        args = {"documentId": document_id, "status": status}
        args.update(kwargs)
        return self.client.mutation("documents:updateDocumentStatus", args)

    def generate_upload_url(self) -> str:
        """Gets a short-lived URL for uploading a file to Convex storage."""
        return self.client.mutation("documents:generateUploadUrl", {})

    def get_download_url(self, storage_id: str) -> str:
        """Gets a download URL for a file in Convex storage."""
        return self.client.query("documents:getDownloadUrl", {
            "storageId": storage_id
        })

    def save_document_metadata(self, clerk_id: str, title: str, filename: str, storage_id: str = None) -> str:
        """Creates a document record in Convex and returns the document ID."""
        args = {
            "clerkId": clerk_id,
            "title": title,
            "filename": filename
        }
        if storage_id:
            args["storageId"] = storage_id
        return self.client.mutation("documents:createDocument", args)

    # ─────────────────────────────────────────────
    # Chat & Memory
    # ─────────────────────────────────────────────

    def create_conversation(self, title: str, clerk_id: str = "frontend_user") -> str:
        """Creates a new conversation thread."""
        return self.client.mutation("conversations:createConversation", {
            "clerkId": clerk_id,
            "title": title
        })

    def list_conversations(self, clerk_id: str = "frontend_user") -> list:
        """Lists all conversations for a user."""
        return self.client.query("conversations:listConversations", {
            "clerkId": clerk_id
        })

    def get_conversation(self, conversation_id: str) -> dict:
        """Gets metadata for a specific conversation."""
        try:
            return self.client.query("conversations:getConversation", {
                "conversationId": conversation_id
            })
        except Exception:
            return None

    def delete_conversation(self, conversation_id: str) -> None:
        """Deletes a conversation and its messages."""
        self.client.mutation("conversations:deleteConversation", {
            "conversationId": conversation_id
        })

    def attach_document_to_conversation(self, conversation_id: str, document_id: str) -> None:
        """Attaches a document to a conversation's scope."""
        self.client.mutation("conversations:attachDocument", {
            "conversationId": conversation_id,
            "documentId": document_id
        })

    def get_conversation_messages(self, conversation_id: str):
        """Retrieves conversational memory for LangGraph."""
        return self.client.query("messages:listMessages", {
            "conversationId": conversation_id
        })

    def save_agent_response(self, conversation_id: str, content: str, sources: list = None, confidence: float = None, latency_ms: float = None, query_type: str = None):
        """Saves the final generator response."""
        args = {
            "conversationId": conversation_id,
            "content": content
        }
        if sources is not None: args["sources"] = sources
        if confidence is not None: args["confidence"] = confidence
        if latency_ms is not None: args["latencyMs"] = latency_ms
        if query_type is not None: args["queryType"] = query_type
        
        return self.client.mutation("messages:saveAgentResponse", args)

    # ─────────────────────────────────────────────
    # Telemetry
    # ─────────────────────────────────────────────
    
    def log_event(self, event_type: str, query_id: str, node_name: str = None, duration_ms: float = None, details: dict = None):
        """Pushes telemetry events to Convex logs."""
        args = {
            "eventType": event_type,
            "queryId": query_id
        }
        if node_name is not None: args["nodeName"] = node_name
        if duration_ms is not None: args["durationMs"] = duration_ms
        if details is not None: args["details"] = details
        
        try:
            self.client.mutation("telemetry:logEvent", args)
        except Exception:
            pass # Swallow telemetry failures to prevent cascading errors

# Global singleton
convex_service = ConvexService()
