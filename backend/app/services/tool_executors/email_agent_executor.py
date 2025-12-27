"""
Email Agent Executor - Handles studio signal execution for email templates.

Educational Note: This executor is triggered by studio signals (from main chat)
and launches the email agent as a background task. Unlike web_agent_executor,
this doesn't handle individual tool calls - those are handled inside
email_agent_service itself.
"""

from typing import Dict, Any
import uuid
from datetime import datetime


class EmailAgentExecutor:
    """
    Executor for email template generation via studio signals.

    Educational Note: The studio signal flow:
    1. User chats with AI about sources
    2. AI decides to activate studio (sends studio_signal tool call)
    3. studio_signal_executor routes to this executor
    4. We create a job and launch email_agent as background task
    5. Agent runs independently and updates job status
    """

    def execute(
        self,
        project_id: str,
        source_id: str,
        direction: str = ""
    ) -> Dict[str, Any]:
        """
        Execute email template generation as a background task.

        Args:
            project_id: The project ID
            source_id: Source to generate template from
            direction: User's direction/guidance (optional)

        Returns:
            Job info with status and job_id for polling
        """
        from app.services.studio_services import studio_index_service
        from app.services.background_services import task_service
        from app.services.ai_agents import email_agent_service
        from app.services.source_services import source_service

        # Get source info
        source = source_service.get_source(project_id, source_id)
        if not source:
            return {
                "success": False,
                "error": f"Source {source_id} not found"
            }

        source_name = source.get("name", "Unknown Source")

        # Create job
        job_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()

        studio_index_service.create_email_job(
            project_id=project_id,
            job_id=job_id,
            source_id=source_id,
            source_name=source_name,
            direction=direction
        )

        # Launch agent as background task
        def run_agent():
            """Background task to run the email agent."""
            print(f"[EmailAgentExecutor] Starting email agent for job {job_id[:8]}")
            try:
                email_agent_service.generate_template(
                    project_id=project_id,
                    source_id=source_id,
                    job_id=job_id,
                    direction=direction
                )
            except Exception as e:
                print(f"[EmailAgentExecutor] Error in email agent: {e}")
                import traceback
                traceback.print_exc()
                # Update job on error
                studio_index_service.update_email_job(
                    project_id, job_id,
                    status="error",
                    error_message=str(e)
                )

        task_service.submit_task(
            task_type="email_template_generation",
            target_id=job_id,
            callable_func=run_agent
        )

        return {
            "success": True,
            "job_id": job_id,
            "status": "processing",
            "message": f"Email template generation started for '{source_name}'"
        }


# Singleton instance
email_agent_executor = EmailAgentExecutor()
