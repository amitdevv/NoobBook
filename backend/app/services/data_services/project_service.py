"""
Project Service - Business logic for project management.

Educational Note: This service layer handles all project-related operations
using Supabase as the database backend. It provides a clean abstraction
over database operations.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any

from app.services.integrations.supabase import get_supabase, is_supabase_enabled


# Default user ID for single-user mode
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


class ProjectService:
    """
    Service class for managing projects using Supabase.

    Educational Note: This service uses Supabase's PostgREST API for
    database operations. Each method maps to SQL queries under the hood.
    """

    def __init__(self):
        """Initialize the project service."""
        if not is_supabase_enabled():
            raise RuntimeError(
                "Supabase is not configured. Please add SUPABASE_URL and "
                "SUPABASE_ANON_KEY to your .env file."
            )
        self.supabase = get_supabase()
        self.table = "projects"

    def list_all_projects(self) -> List[Dict[str, Any]]:
        """
        List all available projects.

        Returns:
            List of project metadata sorted by last_accessed (most recent first)

        Educational Note: Supabase's select() returns a response object.
        We access .data to get the actual records.
        """
        response = (
            self.supabase.table(self.table)
            .select("id, name, description, created_at, updated_at, last_accessed, costs")
            .eq("user_id", DEFAULT_USER_ID)
            .order("last_accessed", desc=True)
            .execute()
        )
        return response.data or []

    def create_project(self, name: str, description: str = "") -> Dict[str, Any]:
        """
        Create a new project.

        Args:
            name: Project name
            description: Optional project description

        Returns:
            Created project object

        Raises:
            ValueError: If project name already exists

        Educational Note: Supabase's insert() returns the inserted row(s).
        We use .select() after insert to get the full record back.
        """
        # Check if project name already exists
        existing = (
            self.supabase.table(self.table)
            .select("id")
            .eq("user_id", DEFAULT_USER_ID)
            .ilike("name", name)
            .execute()
        )

        if existing.data:
            raise ValueError(f"Project with name '{name}' already exists")

        # Create project data
        project_data = {
            "user_id": DEFAULT_USER_ID,
            "name": name,
            "description": description,
            "custom_prompt": None,
            "memory": {},
            "costs": {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost_usd": 0,
                "by_model": {}
            }
        }

        # Insert and return the new project
        response = (
            self.supabase.table(self.table)
            .insert(project_data)
            .execute()
        )

        if response.data:
            project = response.data[0]
            print(f"Created project: {name} (ID: {project['id']})")
            return self._format_project_metadata(project)

        raise RuntimeError("Failed to create project")

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full project data by ID.

        Args:
            project_id: The project UUID

        Returns:
            Full project data or None if not found

        Educational Note: We update last_accessed on every get to track
        when the project was last opened.
        """
        response = (
            self.supabase.table(self.table)
            .select("*")
            .eq("id", project_id)
            .eq("user_id", DEFAULT_USER_ID)
            .execute()
        )

        if not response.data:
            return None

        project = response.data[0]

        # Update last accessed time
        self.supabase.table(self.table).update({
            "last_accessed": datetime.now().isoformat()
        }).eq("id", project_id).execute()

        return project

    def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update project metadata.

        Args:
            project_id: The project UUID
            name: New name (optional)
            description: New description (optional)

        Returns:
            Updated project metadata or None if not found

        Raises:
            ValueError: If new name conflicts with existing project
        """
        # Check if project exists
        project = self.get_project(project_id)
        if not project:
            return None

        # Check if new name conflicts with existing project
        if name and name != project["name"]:
            existing = (
                self.supabase.table(self.table)
                .select("id")
                .eq("user_id", DEFAULT_USER_ID)
                .ilike("name", name)
                .neq("id", project_id)
                .execute()
            )
            if existing.data:
                raise ValueError(f"Project with name '{name}' already exists")

        # Build update data
        update_data = {}
        if name:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description

        if not update_data:
            return self._format_project_metadata(project)

        # Update project
        response = (
            self.supabase.table(self.table)
            .update(update_data)
            .eq("id", project_id)
            .execute()
        )

        if response.data:
            print(f"Updated project: {project_id}")
            return self._format_project_metadata(response.data[0])

        return None

    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project.

        Args:
            project_id: The project UUID

        Returns:
            True if deleted, False if not found

        Educational Note: Supabase cascades deletes automatically based on
        foreign key constraints. Deleting a project also deletes its
        sources, chats, messages, etc.
        """
        # Check if project exists first
        existing = (
            self.supabase.table(self.table)
            .select("id")
            .eq("id", project_id)
            .eq("user_id", DEFAULT_USER_ID)
            .execute()
        )

        if not existing.data:
            return False

        # Delete the project
        self.supabase.table(self.table).delete().eq("id", project_id).execute()

        print(f"Deleted project: {project_id}")
        return True

    def open_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Open a project (update last accessed time).

        Args:
            project_id: The project UUID

        Returns:
            Project metadata or None if not found
        """
        project = self.get_project(project_id)
        if not project:
            return None

        return self._format_project_metadata(project)

    def update_custom_prompt(
        self,
        project_id: str,
        custom_prompt: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Update the project's custom system prompt.

        Args:
            project_id: The project UUID
            custom_prompt: The custom prompt string, or None to reset to default

        Returns:
            Updated project or None if project not found
        """
        # Check if project exists
        existing = (
            self.supabase.table(self.table)
            .select("id")
            .eq("id", project_id)
            .eq("user_id", DEFAULT_USER_ID)
            .execute()
        )

        if not existing.data:
            return None

        # Update custom prompt
        response = (
            self.supabase.table(self.table)
            .update({"custom_prompt": custom_prompt})
            .eq("id", project_id)
            .execute()
        )

        if response.data:
            print(f"Updated custom prompt for project: {project_id}")
            return response.data[0]

        return None

    def get_project_settings(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the project's settings.

        Args:
            project_id: The project UUID

        Returns:
            Project settings or None if project not found
        """
        response = (
            self.supabase.table(self.table)
            .select("custom_prompt, memory")
            .eq("id", project_id)
            .eq("user_id", DEFAULT_USER_ID)
            .execute()
        )

        if not response.data:
            return None

        project = response.data[0]

        # Return settings with defaults
        return {
            "ai_model": "claude-sonnet-4-5-20250929",
            "auto_save": True,
            "custom_prompt": project.get("custom_prompt")
        }

    def get_project_costs(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the project's API usage costs.

        Args:
            project_id: The project UUID

        Returns:
            Project costs or None if project not found
        """
        response = (
            self.supabase.table(self.table)
            .select("costs")
            .eq("id", project_id)
            .eq("user_id", DEFAULT_USER_ID)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0].get("costs", {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": 0,
            "by_model": {}
        })

    def update_project_costs(self, project_id: str, costs: Dict[str, Any]) -> bool:
        """
        Update the project's API usage costs.

        Args:
            project_id: The project UUID
            costs: Updated costs dictionary

        Returns:
            True if updated, False if project not found
        """
        response = (
            self.supabase.table(self.table)
            .update({"costs": costs})
            .eq("id", project_id)
            .execute()
        )

        return bool(response.data)

    def get_project_memory(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the project's memory.

        Args:
            project_id: The project UUID

        Returns:
            Project memory or None if project not found
        """
        response = (
            self.supabase.table(self.table)
            .select("memory")
            .eq("id", project_id)
            .eq("user_id", DEFAULT_USER_ID)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0].get("memory", {})

    def update_project_memory(self, project_id: str, memory: Dict[str, Any]) -> bool:
        """
        Update the project's memory.

        Args:
            project_id: The project UUID
            memory: Updated memory dictionary

        Returns:
            True if updated, False if project not found
        """
        response = (
            self.supabase.table(self.table)
            .update({"memory": memory})
            .eq("id", project_id)
            .execute()
        )

        return bool(response.data)

    # ==================== User Memory Methods ====================

    def get_user_memory(self) -> Optional[str]:
        """
        Get the user's global memory.

        Educational Note: User memory persists across all projects
        and stores global preferences like name, communication style, etc.

        Returns:
            User memory string or None if not found
        """
        response = (
            self.supabase.table("users")
            .select("memory")
            .eq("id", DEFAULT_USER_ID)
            .execute()
        )

        if not response.data:
            return None

        memory_data = response.data[0].get("memory", {})
        return memory_data.get("memory") if memory_data else None

    def update_user_memory(self, memory: str) -> bool:
        """
        Update the user's global memory.

        Args:
            memory: The memory content string

        Returns:
            True if updated successfully
        """
        from datetime import datetime

        memory_data = {
            "memory": memory,
            "updated_at": datetime.now().isoformat()
        }

        response = (
            self.supabase.table("users")
            .update({"memory": memory_data})
            .eq("id", DEFAULT_USER_ID)
            .execute()
        )

        return bool(response.data)

    def _format_project_metadata(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format project data to return only metadata fields.

        Educational Note: This helper ensures consistent response format
        and excludes large fields like memory and full settings.
        """
        return {
            "id": project["id"],
            "name": project["name"],
            "description": project.get("description", ""),
            "created_at": project["created_at"],
            "updated_at": project["updated_at"],
            "last_accessed": project.get("last_accessed", project["updated_at"]),
            "costs": project.get("costs", {})
        }


# Singleton instance
project_service = ProjectService()
