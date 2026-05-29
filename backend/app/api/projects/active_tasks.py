"""
Active Tasks endpoint - returns all in-progress tasks for a project.

Provides a single consolidated endpoint for the frontend
status bar to poll. Aggregates sources being processed, studio jobs in progress,
and background tasks into a unified list.
"""

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
                    # Show ticket count + throughput for Freshdesk sources during sync
                    processing_info = src.get("processing_info") or {}
                    tickets_fetched = processing_info.get("tickets_fetched")
                    tickets_per_sec = processing_info.get("tickets_per_sec")
                    rate_limit = processing_info.get("rate_limit")
                    if tickets_fetched is not None:
                        detail = f"Fetched {tickets_fetched:,} tickets"
                        if tickets_per_sec:
                            detail += f" ({tickets_per_sec:.0f}/sec)"
                        elif rate_limit:
                            detail += f" ({rate_limit} req/min)"
                        detail += "..."
                    else:
                        detail = f"{'Embedding' if status == 'embedding' else 'Processing'}..."

                    tasks.append({
                        "id": src.get("id"),
                        "type": "source",
                        "label": src.get("name", "Source"),
                        "detail": detail,
                        "status": status,
                        "target_id": src.get("id"),
                        "created_at": src.get("created_at"),
                    })
        except Exception as e:
            current_app.logger.warning(f"Error fetching sources for active tasks: {e}")

        # 2. Studio jobs in progress
        # Tracks which studio_jobs.id values we've already emitted so the
        # background_tasks pass below can dedupe by target_id (every studio
        # agent emits both a studio_jobs row AND a background_tasks row via
        # task_service.submit_task(target_id=job_id) — the bg row is
        # internal plumbing and shouldn't render as a separate task).
        studio_job_indices: dict[str, int] = {}
        try:
            supabase = get_supabase()
            jobs_response = (
                supabase.table("studio_jobs")
                .select("id, job_type, source_name, direction, status, progress, status_message, created_at")
                .eq("project_id", project_id)
                .in_("status", ["pending", "processing"])
                .order("created_at", desc=False)
                .execute()
            )
            for job in (jobs_response.data or []):
                job_type = job.get("job_type", "unknown")
                label = _format_job_type(job_type)
                job_id = job.get("id")

                studio_job_indices[job_id] = len(tasks)
                tasks.append({
                    "id": job_id,
                    "type": "studio",
                    "label": label,
                    "detail": _studio_job_detail(job),
                    "status": job.get("status"),
                    "progress": job.get("progress"),
                    "target_id": job_id,
                    "created_at": job.get("created_at"),
                })
        except Exception as e:
            current_app.logger.warning(f"Error fetching studio jobs for active tasks: {e}")

        # 3. Background tasks (catch anything else running)
        try:
            supabase = get_supabase()
            bg_response = (
                supabase.table("background_tasks")
                .select("id, task_type, target_id, target_type, status, message, created_at, started_at")
                .in_("status", ["pending", "running"])
                .order("created_at", desc=False)
                .execute()
            )
            for task in (bg_response.data or []):
                target_id = task.get("target_id")
                # If this bg task is the executor row for a studio job we've
                # already emitted, merge a live message into the studio row's
                # detail (when informative) and skip rendering as a separate
                # row. This is what closes #235.
                if target_id and target_id in studio_job_indices:
                    bg_message = (task.get("message") or "").strip()
                    if bg_message and bg_message.lower() != "processing...":
                        studio_task = tasks[studio_job_indices[target_id]]
                        studio_task["detail"] = bg_message
                    continue

                task_type = task.get("task_type", "unknown")
                tasks.append({
                    "id": task.get("id"),
                    "type": "background",
                    "task_type": task_type,
                    "label": _format_task_type(task_type),
                    "detail": task.get("message") or "Processing...",
                    "status": task.get("status"),
                    "target_id": target_id,
                    "target_type": task.get("target_type"),
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


# Generic placeholders that the studio agents seed status_message with
# before any real progress lands. Treated as not-yet-informative so the
# detail line falls back to source_name / direction instead of a useless
# "Initializing..." placeholder while the row is fresh.
_GENERIC_STATUS_MESSAGES = {"", "initializing...", "initializing", "processing..."}


def _studio_job_detail(job: dict) -> str:
    """Build the detail line for an in-flight studio job row.

    Prefers `status_message` from the agent (e.g. "Writing intro section…")
    when it's informative, otherwise falls back to source name → direction
    → generic placeholder. Keeps the user-visible row honest about what
    the agent is actually doing right now.
    """
    status_message = (job.get("status_message") or "").strip()
    if status_message and status_message.lower() not in _GENERIC_STATUS_MESSAGES:
        return status_message
    if job.get("source_name"):
        return job["source_name"]
    if job.get("direction"):
        return job["direction"]
    return "Generating..."


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
