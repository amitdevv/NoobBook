"""
Active Tasks endpoint - returns all in-progress tasks for a project.

Educational Note: Provides a single consolidated endpoint for the frontend
status bar to poll. Aggregates sources being processed, studio jobs in progress,
and background tasks into a unified list.
"""

from datetime import datetime
from flask import jsonify, current_app

from app.api.projects import projects_bp
from app.services.source_services import source_service
from app.services.integrations.supabase import get_supabase


@projects_bp.route("/projects/<project_id>/active-tasks", methods=["GET"])
def get_active_tasks(project_id: str):
    """
    Get all active/in-progress tasks for a project.

    Returns a unified list of:
    - Sources being processed (status: processing, embedding)
    - Studio jobs in progress (status: pending, processing)
    - Background tasks running (status: pending, running)
    """
    try:
        tasks = []

        # 1. Sources being processed
        try:
            sources = source_service.list_sources(project_id)
            for src in sources:
                status = src.get("status", "")
                if status in ("processing", "embedding", "uploaded"):
                    # Only include "uploaded" if it was very recently created (within 30s)
                    # to catch the brief window before processing starts
                    if status == "uploaded":
                        continue
                    # Show ticket count for Freshdesk sources during sync
                    processing_info = src.get("processing_info") or {}
                    tickets_fetched = processing_info.get("tickets_fetched")
                    if tickets_fetched is not None:
                        detail = f"Fetched {tickets_fetched} tickets..."
                    else:
                        detail = f"{'Embedding' if status == 'embedding' else 'Processing'}..."

                    tasks.append({
                        "id": src.get("id"),
                        "type": "source",
                        "label": src.get("name", "Source"),
                        "detail": detail,
                        "status": status,
                        "created_at": src.get("created_at"),
                    })
        except Exception as e:
            current_app.logger.warning(f"Error fetching sources for active tasks: {e}")

        # 2. Studio jobs in progress
        try:
            supabase = get_supabase()
            jobs_response = (
                supabase.table("studio_jobs")
                .select("id, job_type, source_name, direction, status, progress, created_at")
                .eq("project_id", project_id)
                .in_("status", ["pending", "processing"])
                .order("created_at", desc=False)
                .execute()
            )
            for job in (jobs_response.data or []):
                job_type = job.get("job_type", "unknown")
                label = _format_job_type(job_type)
                detail = job.get("direction") or "Generating..."
                if job.get("source_name"):
                    detail = job.get("source_name")

                tasks.append({
                    "id": job.get("id"),
                    "type": "studio",
                    "label": label,
                    "detail": detail,
                    "status": job.get("status"),
                    "progress": job.get("progress"),
                    "created_at": job.get("created_at"),
                })
        except Exception as e:
            current_app.logger.warning(f"Error fetching studio jobs for active tasks: {e}")

        # 3. Background tasks (catch anything else running)
        try:
            supabase = get_supabase()
            bg_response = (
                supabase.table("background_tasks")
                .select("id, task_type, target_type, status, message, created_at, started_at")
                .in_("status", ["pending", "running"])
                .order("created_at", desc=False)
                .execute()
            )
            # Only include bg tasks not already covered by sources/studio
            existing_ids = {t["id"] for t in tasks}
            for task in (bg_response.data or []):
                if task.get("id") in existing_ids:
                    continue
                task_type = task.get("task_type", "unknown")
                tasks.append({
                    "id": task.get("id"),
                    "type": "background",
                    "label": _format_task_type(task_type),
                    "detail": task.get("message") or "Processing...",
                    "status": task.get("status"),
                    "created_at": task.get("started_at") or task.get("created_at"),
                })
        except Exception as e:
            current_app.logger.warning(f"Error fetching background tasks: {e}")

        return jsonify({
            "success": True,
            "tasks": tasks,
            "count": len(tasks),
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting active tasks for project {project_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _format_job_type(job_type: str) -> str:
    """Convert job_type slug to a display label."""
    labels = {
        "audio": "Audio Overview",
        "video": "Video Overview",
        "presentation": "Presentation",
        "quiz": "Quiz",
        "mind_map": "Mind Map",
        "flash_cards": "Flash Cards",
        "emails": "Email Draft",
        "websites": "Website",
        "components": "Component",
        "wireframes": "Wireframe",
        "flow_diagrams": "Flow Diagram",
        "blog": "Blog Post",
        "prd": "PRD",
    }
    return labels.get(job_type, job_type.replace("_", " ").title())


def _format_task_type(task_type: str) -> str:
    """Convert task_type to a display label."""
    labels = {
        "source_processing": "Processing Source",
        "source_summarization": "Summarizing",
        "chat_auto_name": "Naming Chat",
    }
    return labels.get(task_type, task_type.replace("_", " ").title())
