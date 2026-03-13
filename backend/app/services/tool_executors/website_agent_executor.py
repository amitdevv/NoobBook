"""
Website Agent Executor - Handles studio signal execution for website generation.

Educational Note: This executor is triggered by studio signals (from main chat)
and launches the website agent as a background task. Similar to email_agent_executor,
tool calls are handled inside website_agent_service itself.
"""

import logging
from typing import Dict, Any, Optional
import uuid

logger = logging.getLogger(__name__)


class WebsiteAgentExecutor:
    """
    Executor for website generation via studio signals.

    Educational Note: The studio signal flow:
    1. User chats with AI about sources
    2. AI decides to activate studio (sends studio_signal tool call)
    3. studio_signal_executor routes to this executor
    4. We create a job and launch website_agent as background task
    5. Agent runs independently and updates job status
    """

    def execute(
        self,
        project_id: str,
        source_id: str,
        direction: str = "",
        edit_instructions: Optional[str] = None,
        previous_markdown: Optional[str] = None,
        previous_title: Optional[str] = None,
        parent_job_id: Optional[str] = None,
        parent_source_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute website generation as a background task.

        Args:
            project_id: The project ID
            source_id: Source to generate website from
            direction: User's direction/guidance (optional)
            edit_instructions: Instructions for refining a previous website (optional)
            previous_markdown: File content from a parent job to refine (optional)
            previous_title: Site name from a parent job (optional)
            parent_job_id: UUID of the parent job being edited (optional)
            parent_source_name: Source name from parent job (optional)

        Returns:
            Job info with status and job_id for polling
        """
        from app.services.studio_services import studio_index_service
        from app.services.background_services import task_service
        from app.services.ai_agents import website_agent_service
        from app.services.source_services import source_service

        # Get source info
        source_name = "No Source"
        if source_id:
            source = source_service.get_source(project_id, source_id)
            if not source:
                if previous_markdown:
                    # Edit mode — source may be deleted; inherit name from parent job
                    source_name = parent_source_name or "No Source"
                else:
                    return {
                        "success": False,
                        "error": f"Source {source_id} not found"
                    }
            else:
                source_name = source.get("name", "Unknown Source")

        # Create job
        job_id = str(uuid.uuid4())

        studio_index_service.create_website_job(
            project_id=project_id,
            job_id=job_id,
            source_id=source_id,
            source_name=source_name,
            direction=direction,
            parent_job_id=parent_job_id,
            edit_instructions=edit_instructions
        )

        # Launch agent as background task
        def run_agent():
            """Background task to run the website agent."""
            logger.info("Starting website agent for job %s", job_id[:8])
            try:
                website_agent_service.generate_website(
                    project_id=project_id,
                    source_id=source_id,
                    job_id=job_id,
                    direction=direction,
                    edit_instructions=edit_instructions,
                    previous_markdown=previous_markdown,
                    previous_title=previous_title
                )
            except Exception as e:
                logger.exception("Website agent failed for job %s", job_id[:8])
                # Update job on error
                studio_index_service.update_website_job(
                    project_id, job_id,
                    status="error",
                    error_message=str(e)
                )

        task_service.submit_task(
            task_type="website_generation",
            target_id=job_id,
            callable_func=run_agent
        )

        return {
            "success": True,
            "job_id": job_id,
            "status": "processing",
            "message": f"Website generation started for '{source_name}'"
        }


# Singleton instance
website_agent_executor = WebsiteAgentExecutor()
