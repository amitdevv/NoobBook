"""
Presentation Agent Executor - Handles studio signal execution for presentation generation.

Educational Note: This executor is triggered by studio signals (from main chat)
and launches the presentation agent as a background task. After the agent generates
HTML slides, it captures screenshots and exports to PPTX.
"""

import logging
import shutil
import tempfile
from typing import Dict, Any
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


class PresentationAgentExecutor:
    """
    Executor for presentation generation via studio signals.

    Educational Note: The studio signal flow:
    1. User chats with AI about sources
    2. AI decides to activate studio (sends studio_signal tool call)
    3. studio_signal_executor routes to this executor
    4. We create a job and launch presentation_agent as background task
    5. Agent generates HTML slides
    6. We capture screenshots and export to PPTX
    7. Job status is updated throughout
    """

    def execute(
        self,
        project_id: str,
        source_id: str,
        direction: str = ""
    ) -> Dict[str, Any]:
        """
        Execute presentation generation as a background task.

        Args:
            project_id: The project ID
            source_id: Source to generate presentation from
            direction: User's direction/guidance (optional)

        Returns:
            Job info with status and job_id for polling
        """
        from app.services.studio_services import studio_index_service
        from app.services.background_services import task_service
        from app.services.ai_agents import presentation_agent_service
        from app.services.source_services import source_service
        from app.services.integrations.supabase import storage_service
        from app.utils.screenshot_utils import capture_slides_as_screenshots
        from app.utils.presentation_export_utils import create_pptx_from_screenshots

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

        studio_index_service.create_presentation_job(
            project_id=project_id,
            job_id=job_id,
            source_id=source_id,
            source_name=source_name,
            direction=direction
        )

        # Launch agent as background task
        def run_agent():
            """Background task to run the presentation agent and export to PPTX."""
            logger.info("Starting presentation agent for job %s", job_id[:8])
            temp_dir = None
            try:
                # Phase 1: Generate HTML slides (writes to Supabase Storage)
                result = presentation_agent_service.generate_presentation(
                    project_id=project_id,
                    source_id=source_id,
                    job_id=job_id,
                    direction=direction
                )

                if not result.get("success"):
                    logger.error("Presentation agent failed: %s", result.get("error_message"))
                    return

                # Phase 2: Capture screenshots and export to PPTX
                slide_files = result.get("slide_files", [])
                if not slide_files:
                    logger.warning("No slides to export for job %s", job_id[:8])
                    return

                # Update status
                studio_index_service.update_presentation_job(
                    project_id, job_id,
                    status_message="Capturing screenshots...",
                    export_status="exporting"
                )

                # Create temp directory and download slides from Supabase for Playwright
                temp_dir = tempfile.mkdtemp(prefix="noobbook_pres_")
                slides_dir = Path(temp_dir) / "slides"
                slides_dir.mkdir()
                screenshots_dir = Path(temp_dir) / "screenshots"
                screenshots_dir.mkdir()

                # Download slide HTML files and base-styles.css to temp dir
                for slide_file in slide_files:
                    content = storage_service.download_studio_file(
                        project_id, "presentations", job_id, f"slides/{slide_file}"
                    )
                    if content:
                        (slides_dir / slide_file).write_text(content, encoding="utf-8")

                # Download base-styles.css
                css_content = storage_service.download_studio_file(
                    project_id, "presentations", job_id, "slides/base-styles.css"
                )
                if css_content:
                    (slides_dir / "base-styles.css").write_text(css_content, encoding="utf-8")

                # Capture screenshots using Playwright against temp dir
                screenshots = capture_slides_as_screenshots(
                    slides_dir=str(slides_dir),
                    output_dir=str(screenshots_dir),
                    slide_files=slide_files
                )

                if not screenshots:
                    logger.error("Screenshot capture failed for job %s", job_id[:8])
                    studio_index_service.update_presentation_job(
                        project_id, job_id,
                        export_status="error",
                        status_message="Screenshot capture failed"
                    )
                    return

                # Upload screenshots to Supabase Storage
                for screenshot_info in screenshots:
                    screenshot_path = Path(screenshot_info.get("screenshot_path", ""))
                    if screenshot_path.exists():
                        screenshot_bytes = screenshot_path.read_bytes()
                        storage_service.upload_studio_binary(
                            project_id=project_id,
                            job_type="presentations",
                            job_id=job_id,
                            filename=f"screenshots/{screenshot_path.name}",
                            file_data=screenshot_bytes,
                            content_type="image/png"
                        )

                # Update with screenshots info
                studio_index_service.update_presentation_job(
                    project_id, job_id,
                    screenshots=screenshots,
                    status_message="Creating PPTX..."
                )

                # Create PPTX in temp dir
                job = studio_index_service.get_presentation_job(project_id, job_id)
                title = job.get("presentation_title", "Presentation") if job else "Presentation"

                # Sanitize filename
                safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
                if not safe_title:
                    safe_title = "Presentation"
                pptx_filename = f"{safe_title}.pptx"

                pptx_path = Path(temp_dir) / pptx_filename

                pptx_result = create_pptx_from_screenshots(
                    screenshots=screenshots,
                    output_path=str(pptx_path),
                    title=title
                )

                if pptx_result:
                    # Upload PPTX to Supabase Storage
                    pptx_bytes = pptx_path.read_bytes()
                    storage_service.upload_studio_binary(
                        project_id=project_id,
                        job_type="presentations",
                        job_id=job_id,
                        filename=pptx_filename,
                        file_data=pptx_bytes,
                        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )

                    # Store filename (not absolute path) in job metadata
                    studio_index_service.update_presentation_job(
                        project_id, job_id,
                        pptx_file=pptx_filename,
                        pptx_filename=pptx_filename,
                        export_status="ready",
                        status_message="Presentation ready for download!",
                        download_url=f"/api/v1/projects/{project_id}/studio/presentations/{job_id}/download"
                    )
                    logger.info("PPTX created: %s", pptx_filename)
                else:
                    studio_index_service.update_presentation_job(
                        project_id, job_id,
                        export_status="error",
                        status_message="PPTX export failed"
                    )
                    logger.error("PPTX export failed for job %s", job_id[:8])

            except Exception as e:
                logger.exception("Presentation agent failed for job %s", job_id[:8])
                # Update job on error
                studio_index_service.update_presentation_job(
                    project_id, job_id,
                    status="error",
                    error_message=str(e)
                )
            finally:
                # Clean up temp directory
                if temp_dir and Path(temp_dir).exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)

        task_service.submit_task(
            task_type="presentation_generation",
            target_id=job_id,
            callable_func=run_agent
        )

        return {
            "success": True,
            "job_id": job_id,
            "status": "processing",
            "message": f"Presentation generation started for '{source_name}'"
        }


# Singleton instance
presentation_agent_executor = PresentationAgentExecutor()
