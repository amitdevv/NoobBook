"""
Memory Executor - Execute memory tool calls from main chat.

Educational Note: This executor handles the store_memory tool when Claude
decides to save user or project memory. The execution flow is:

1. Main chat Claude calls store_memory tool with user_memory/project_memory
2. This executor immediately returns "memory stored" (non-blocking)
3. Actual memory merge runs in a background thread (fire-and-forget)
4. Background thread uses memory_service to merge with AI and save

Why not task_service? Memory updates are fire-and-forget — they don't need
the task tracking (status, progress, cancellation) that task_service provides.
Using a simple thread avoids UUID/RLS issues with the background_tasks table.
"""
import logging
import threading
from typing import Dict, Any, Optional

from app.services.ai_services.memory_service import memory_service

logger = logging.getLogger(__name__)


class MemoryExecutor:
    """
    Executor for store_memory tool calls.

    Educational Note: Provides immediate response to tool call while
    delegating actual work to background task for non-blocking operation.
    """

    def execute(
        self,
        project_id: str,
        user_memory: Optional[str] = None,
        project_memory: Optional[str] = None,
        why_generated: str = "",
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute the store_memory tool call.

        Educational Note: This method:
        1. Validates inputs
        2. Queues background tasks for memory updates
        3. Returns immediate success (non-blocking)

        Args:
            project_id: The project UUID (needed for project memory)
            user_memory: Optional user-level memory to store
            project_memory: Optional project-level memory to store
            why_generated: Reason for storing this memory

        Returns:
            Dict with immediate success response
        """
        # Track what we're storing
        storing = []

        # Run user memory update in background thread if provided
        if user_memory and user_memory.strip():
            thread = threading.Thread(
                target=self._update_user_memory,
                kwargs=dict(new_memory=user_memory, reason=why_generated, user_id=user_id),
                daemon=True,
            )
            thread.start()
            storing.append("user memory")
            logger.info("Started user memory update: %s...", user_memory[:50])

        # Run project memory update in background thread if provided
        if project_memory and project_memory.strip():
            thread = threading.Thread(
                target=self._update_project_memory,
                kwargs=dict(
                    project_id_for_memory=project_id,
                    new_memory=project_memory,
                    reason=why_generated,
                    user_id=user_id,
                ),
                daemon=True,
            )
            thread.start()
            storing.append("project memory")
            logger.info("Started project memory update: %s...", project_memory[:50])

        # Return immediate success
        if storing:
            return {
                "success": True,
                "message": f"Memory update queued: {', '.join(storing)}",
                "reason": why_generated
            }
        else:
            return {
                "success": False,
                "message": "No memory content provided to store"
            }

    def _update_user_memory(
        self,
        new_memory: str,
        reason: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Background thread to update user memory.

        Educational Note: This runs in a daemon thread (fire-and-forget).
        It calls memory_service which uses AI to merge memories.
        """
        try:
            result = memory_service.update_memory(
                memory_type="user",
                new_memory=new_memory,
                reason=reason,
                user_id=user_id,
            )
            if result.get("success"):
                logger.info("User memory updated successfully")
            else:
                logger.error("User memory update failed: %s", result.get("error"))
        except Exception as e:
            logger.exception("Error in user memory update thread: %s", e)

    def _update_project_memory(
        self,
        project_id_for_memory: str,
        new_memory: str,
        reason: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Background thread to update project memory.

        Educational Note: This runs in a daemon thread (fire-and-forget).
        It calls memory_service which uses AI to merge memories.
        """
        try:
            result = memory_service.update_memory(
                memory_type="project",
                new_memory=new_memory,
                reason=reason,
                project_id=project_id_for_memory,
                user_id=user_id,
            )
            if result.get("success"):
                logger.info("Project memory updated successfully")
            else:
                logger.error("Project memory update failed: %s", result.get("error"))
        except Exception as e:
            logger.exception("Error in project memory update thread: %s", e)


# Singleton instance
memory_executor = MemoryExecutor()
