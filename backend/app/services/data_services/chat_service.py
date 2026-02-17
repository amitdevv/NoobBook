"""
Chat Service - CRUD operations for chat entities.

Educational Note: This service manages chat entity lifecycle within projects
using Supabase as the database backend.

Separation of Concerns:
- chat_service.py: Chat CRUD (this file)
- claude_service.py: Claude API interactions
- message_service.py: Message persistence
- prompt_loader.py: Prompt management
"""
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

from app.services.integrations.supabase import get_supabase, is_supabase_enabled

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service class for chat entity management using Supabase.

    Educational Note: A chat is a conversation container within a project.
    It has metadata (title, timestamps) and holds messages.
    """

    def __init__(self):
        """Initialize the chat service."""
        if not is_supabase_enabled():
            raise RuntimeError(
                "Supabase is not configured. Please add SUPABASE_URL and "
                "SUPABASE_ANON_KEY to your .env file."
            )
        self.supabase = get_supabase()
        self.table = "chats"
        self.messages_table = "messages"
        self.studio_signals_table = "studio_signals"

    def list_chats(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List all chats for a project.

        Educational Note: Returns metadata only (not full messages) for
        efficient loading of chat lists in the UI.

        Args:
            project_id: The project UUID

        Returns:
            List of chat metadata, sorted by most recent first
        """
        response = (
            self.supabase.table(self.table)
            .select("id, title, created_at, updated_at")
            .eq("project_id", project_id)
            .order("updated_at", desc=True)
            .execute()
        )

        chats = response.data or []

        # Add message count for each chat
        for chat in chats:
            count_response = (
                self.supabase.table(self.messages_table)
                .select("id", count="exact")
                .eq("chat_id", chat["id"])
                .execute()
            )
            chat["message_count"] = count_response.count or 0

        return chats

    def create_chat(self, project_id: str, title: str = "New Chat") -> Dict[str, Any]:
        """
        Create a new chat in a project.

        Educational Note: Initializes an empty conversation with metadata.
        Messages are added separately via message_service.

        Args:
            project_id: The project UUID
            title: Initial chat title

        Returns:
            Created chat metadata
        """
        chat_data = {
            "project_id": project_id,
            "title": title
        }

        response = (
            self.supabase.table(self.table)
            .insert(chat_data)
            .execute()
        )

        if response.data:
            chat = response.data[0]
            return {
                "id": chat["id"],
                "title": chat["title"],
                "created_at": chat["created_at"],
                "updated_at": chat["updated_at"],
                "message_count": 0
            }

        raise RuntimeError("Failed to create chat")

    def get_chat(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full chat data including messages and studio signals.

        Educational Note: Filters out tool_use and tool_result messages
        from the response. These are internal messages used in the tool
        chain and shouldn't be displayed to users.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            Full chat data or None if not found
        """
        # Get chat metadata
        chat_response = (
            self.supabase.table(self.table)
            .select("*")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        if not chat_response.data:
            return None

        chat = chat_response.data[0]

        # Get messages for this chat
        messages_response = (
            self.supabase.table(self.messages_table)
            .select("*")
            .eq("chat_id", chat_id)
            .order("created_at", desc=False)
            .execute()
        )

        messages = messages_response.data or []

        # Filter out tool_use and tool_result messages for display
        # Keep only user and assistant messages with string content
        display_messages = []
        for msg in messages:
            content = msg.get("content")
            role = msg.get("role")

            # Skip tool_use and tool_result messages
            if role not in ["user", "assistant"]:
                continue

            # Extract text content - stored as {text: "..."} in JSONB
            # Educational Note: Content can also be a list of content blocks
            # (tool_use responses) — extract only text blocks from those.
            if isinstance(content, dict):
                text_content = content.get("text", "")
            elif isinstance(content, str):
                text_content = content
            elif isinstance(content, list):
                # Extract only text blocks, skip tool_use/tool_result blocks
                text_parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                text_content = "\n\n".join(part for part in text_parts if part.strip())
            else:
                text_content = str(content) if content else ""

            # Skip messages with no displayable text (pure tool_use/tool_result)
            if not text_content.strip():
                continue

            # Create a clean message object for frontend
            display_messages.append({
                "id": msg.get("id"),
                "role": role,
                "content": text_content,  # Always a string
                "timestamp": msg.get("created_at"),  # Map created_at to timestamp
                "model": msg.get("model"),
                "citations": msg.get("citations", [])
            })

        # Get studio signals
        signals_response = (
            self.supabase.table(self.studio_signals_table)
            .select("*")
            .eq("chat_id", chat_id)
            .order("created_at", desc=False)
            .execute()
        )

        # Transform signals for frontend format
        # Backend stores: source_ids: ["uuid1", "uuid2"]
        # Frontend expects: sources: [{source_id: "...", chunk_ids: []}]
        formatted_signals = []
        for signal in (signals_response.data or []):
            source_ids = signal.get("source_ids", []) or []
            formatted_signal = {
                "id": signal.get("id"),
                "studio_item": signal.get("studio_item"),
                "direction": signal.get("direction", ""),
                "sources": [{"source_id": sid, "chunk_ids": []} for sid in source_ids],
                "created_at": signal.get("created_at"),
                "status": signal.get("status", "pending")
            }
            formatted_signals.append(formatted_signal)

        chat["messages"] = display_messages
        chat["studio_signals"] = formatted_signals
        chat["message_count"] = len(messages)

        return chat

    def get_chat_metadata(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Get chat metadata only (without messages).

        Educational Note: Useful for quick lookups without loading
        the full message history.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            Chat metadata or None if not found
        """
        response = (
            self.supabase.table(self.table)
            .select("id, title, created_at, updated_at")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        if not response.data:
            return None

        chat = response.data[0]

        # Get message count
        count_response = (
            self.supabase.table(self.messages_table)
            .select("id", count="exact")
            .eq("chat_id", chat_id)
            .execute()
        )
        chat["message_count"] = count_response.count or 0

        return chat

    def update_chat(
        self,
        project_id: str,
        chat_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update chat metadata.

        Educational Note: Currently supports updating title.
        Messages are updated via message_service.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            updates: Dict of fields to update (e.g., {"title": "New Title"})

        Returns:
            Updated chat metadata or None if not found
        """
        # Check if chat exists
        existing = (
            self.supabase.table(self.table)
            .select("id")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        if not existing.data:
            return None

        # Filter allowed updates
        allowed_fields = ["title", "selected_source_ids"]
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return self.get_chat_metadata(project_id, chat_id)

        # Update chat
        response = (
            self.supabase.table(self.table)
            .update(filtered_updates)
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        if response.data:
            chat = response.data[0]
            # Get message count
            count_response = (
                self.supabase.table(self.messages_table)
                .select("id", count="exact")
                .eq("chat_id", chat_id)
                .execute()
            )
            return {
                "id": chat["id"],
                "title": chat["title"],
                "created_at": chat["created_at"],
                "updated_at": chat["updated_at"],
                "message_count": count_response.count or 0
            }

        return None

    def delete_chat(self, project_id: str, chat_id: str) -> bool:
        """
        Delete a chat and all its messages.

        Educational Note: Supabase cascades deletes automatically based on
        foreign key constraints. Deleting a chat also deletes its messages
        and studio signals.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            True if deleted, False if not found
        """
        # Check if chat exists
        existing = (
            self.supabase.table(self.table)
            .select("id")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        if not existing.data:
            return False

        # Delete the chat (messages and signals cascade automatically)
        self.supabase.table(self.table).delete().eq("id", chat_id).eq("project_id", project_id).execute()

        return True

    def sync_chat_to_index(self, project_id: str, chat_id: str) -> bool:
        """
        Sync a chat's metadata (no-op for Supabase version).

        Educational Note: In Supabase, the data is always in sync.
        This method exists for API compatibility.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            True if chat exists
        """
        existing = (
            self.supabase.table(self.table)
            .select("id")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )
        return bool(existing.data)


# Singleton instance for easy import
chat_service = ChatService()
