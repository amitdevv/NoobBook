"""
Wireframe endpoints - AI-generated UI/UX wireframes using Excalidraw.

Educational Note: Wireframes demonstrate visual UI/UX prototyping:
1. Claude analyzes source content for UI requirements
2. Generates Excalidraw element definitions (shapes, text, layout)
3. Frontend renders using Excalidraw React component
4. Users can edit, export to PNG/SVG

Routes:
- POST /projects/<id>/studio/wireframe           - Start generation
- GET  /projects/<id>/studio/wireframe-jobs/<id> - Job status
- GET  /projects/<id>/studio/wireframe-jobs      - List jobs
"""

import uuid
from flask import jsonify, request, current_app
from app.api.studio import studio_bp
from app.services.studio_services import studio_index_service
from app.services.ai_agents.wireframe_agent_service import wireframe_agent_service
from app.services.source_services import source_index_service
from app.services.background_services.task_service import task_service


@studio_bp.route("/projects/<project_id>/studio/wireframe", methods=["POST"])
def generate_wireframe(project_id: str):
    """
    Start wireframe generation or edit as a background task.

    Educational Note: Wireframes are generated from source content using
    Claude to create Excalidraw element definitions for UI prototyping.

    Request Body:
        - source_id: UUID of the source to generate wireframe from (optional)
        - direction: Optional guidance for what to wireframe
        - parent_job_id: UUID of the parent job to edit (optional, for edits)
        - edit_instructions: Instructions for editing the parent wireframe (optional, for edits)

    Response:
        - success: Boolean
        - job_id: ID for polling status
        - message: Status message
    """
    try:
        data = request.get_json() or {}

        source_id = data.get("source_id")
        direction = data.get(
            "direction", "Create a wireframe for the main page layout."
        )

        # Edit mode: load parent job's description as context for refinement
        parent_job_id = data.get("parent_job_id")
        edit_instructions = data.get("edit_instructions")
        previous_content = None

        if parent_job_id:
            # Clean up any previously failed edit jobs for this parent
            try:
                all_jobs = studio_index_service.list_wireframe_jobs(project_id)
                for job in all_jobs:
                    if (job.get("status") == "error"
                            and job.get("parent_job_id") == parent_job_id):
                        studio_index_service.delete_wireframe_job(project_id, job["id"])
            except Exception:
                pass  # Non-critical cleanup -- don't block the new edit

            parent_job = studio_index_service.get_wireframe_job(project_id, parent_job_id)
            if not parent_job or not parent_job.get("elements"):
                return jsonify(
                    {"success": False, "error": "Parent job not found or has no content to edit"}
                ), 404

            # Use description + title as previous content context for the agent
            previous_parts = []
            if parent_job.get("title"):
                previous_parts.append(f"Title: {parent_job['title']}")
            if parent_job.get("description"):
                previous_parts.append(f"Description: {parent_job['description']}")
            # Include element count for context
            previous_parts.append(f"Element count: {parent_job.get('element_count', len(parent_job.get('elements', [])))}")
            previous_content = "\n".join(previous_parts)

            # Inherit source info from parent if not provided
            if not source_id:
                source_id = parent_job.get("source_id")

        # Source is optional — can generate from direction alone
        source_name = "Direction Only"
        if source_id:
            source = source_index_service.get_source_from_index(project_id, source_id)
            if not source:
                return jsonify(
                    {"success": False, "error": f"Source not found: {source_id}"}
                ), 404
            source_name = source.get("name", "Unknown")

        # Create job record
        job_id = str(uuid.uuid4())
        studio_index_service.create_wireframe_job(
            project_id=project_id,
            job_id=job_id,
            source_id=source_id,
            source_name=source_name,
            direction=direction,
            parent_job_id=parent_job_id,
            edit_instructions=edit_instructions,
        )

        # Submit background task
        task_service.submit_task(
            task_type="wireframe",
            target_id=job_id,
            callable_func=wireframe_agent_service.generate_wireframe,
            project_id=project_id,
            source_id=source_id,
            job_id=job_id,
            direction=direction,
            previous_content=previous_content,
            edit_instructions=edit_instructions,
        )

        return jsonify(
            {
                "success": True,
                "job_id": job_id,
                "message": "Wireframe generation started",
                "source_name": source_name,
            }
        ), 202  # 202 Accepted - processing started

    except Exception as e:
        current_app.logger.error(f"Error starting wireframe generation: {e}")
        return jsonify(
            {
                "success": False,
                "error": f"Failed to start wireframe generation: {str(e)}",
            }
        ), 500


@studio_bp.route(
    "/projects/<project_id>/studio/wireframe-jobs/<job_id>", methods=["GET"]
)
def get_wireframe_job_status(project_id: str, job_id: str):
    """
    Get the status of a wireframe generation job.

    Response:
        - success: Boolean
        - job: Job record with status, progress, elements (when ready)
    """
    try:
        job = studio_index_service.get_wireframe_job(project_id, job_id)

        if not job:
            return jsonify({"success": False, "error": f"Job not found: {job_id}"}), 404

        return jsonify({"success": True, "job": job}), 200

    except Exception as e:
        current_app.logger.error(f"Error getting wireframe job status: {e}")
        return jsonify(
            {"success": False, "error": f"Failed to get job status: {str(e)}"}
        ), 500


@studio_bp.route("/projects/<project_id>/studio/wireframe-jobs", methods=["GET"])
def list_wireframe_jobs(project_id: str):
    """
    List all wireframe jobs for a project.

    Query Parameters:
        - source_id: Optional filter by source

    Response:
        - success: Boolean
        - jobs: List of job records
    """
    try:
        source_id = request.args.get("source_id")
        jobs = studio_index_service.list_wireframe_jobs(project_id, source_id)

        # Filter out orphaned failed-edit jobs (error + parent_job_id).
        clean_jobs = [
            job for job in jobs
            if not (job.get("status") == "error" and job.get("parent_job_id"))
        ]

        return jsonify({"success": True, "jobs": clean_jobs, "count": len(clean_jobs)}), 200

    except Exception as e:
        current_app.logger.error(f"Error listing wireframe jobs: {e}")
        return jsonify(
            {"success": False, "error": f"Failed to list jobs: {str(e)}"}
        ), 500
