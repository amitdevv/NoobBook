"""
Infographic endpoints - AI-generated visual summaries.

Educational Note: Infographics demonstrate visual content synthesis:
1. Claude analyzes source and extracts key points
2. Creates structured visual descriptions
3. Gemini Imagen generates the infographic image
4. Single comprehensive image output

Visual Design Pattern:
- Infographics organize information visually
- Include icons, sections, and visual flow
- Colors indicate categories/importance
- Text is minimal, visual is primary

Generation Pipeline:
1. Extract key facts and statistics
2. Organize into visual hierarchy
3. Generate image prompt for Gemini
4. Create and store image file

Routes:
- POST /projects/<id>/studio/infographic           - Start generation
- GET  /projects/<id>/studio/infographic-jobs/<id> - Job status
- GET  /projects/<id>/studio/infographic-jobs      - List jobs
- GET  /projects/<id>/studio/infographics/<job_id>/<file> - Serve image file
"""
import io
import uuid
from flask import jsonify, request, current_app, send_file, g
from app.api.studio import studio_bp
from app.services.studio_services import studio_index_service
from app.services.studio_services.infographic_service import infographic_service
from app.services.source_services import source_index_service
from app.services.integrations.google.imagen_service import imagen_service
from app.services.integrations.supabase import storage_service
from app.services.background_services.task_service import task_service
from app.api.studio.logo_utils import resolve_logo
from app.services.auth import require_permission


@studio_bp.route('/projects/<project_id>/studio/infographic', methods=['POST'])
@require_permission("studio", "infographics")
def generate_infographic(project_id: str):
    """
    Start infographic generation as a background task.

    Educational Note: Infographics are visual summaries that organize source
    content in an educational format with icons, sections, and visual flow.

    Request Body:
        - source_id: UUID of the source (optional - empty string for no source)
        - direction: Optional guidance for what to focus on
        - parent_job_id: Optional parent job ID for iterative editing
        - edit_instructions: Optional edit instructions (requires parent_job_id)

    Response:
        - success: Boolean
        - job_id: ID for polling status
        - message: Status message
    """
    try:
        data = request.get_json() or {}

        source_id = data.get('source_id', '')
        direction = data.get('direction', 'Create an informative infographic summarizing the key concepts.')

        # Edit mode: load parent job's image prompt as context for refinement
        parent_job_id = data.get("parent_job_id")
        edit_instructions = data.get("edit_instructions")
        previous_image_prompt = None

        if parent_job_id:
            # Clean up any previously failed edit jobs for this parent
            try:
                all_jobs = studio_index_service.list_infographic_jobs(project_id)
                for job in all_jobs:
                    if (job.get("status") == "error"
                            and job.get("parent_job_id") == parent_job_id):
                        studio_index_service.delete_infographic_job(project_id, job["id"])
            except Exception:
                pass  # Non-critical cleanup

            parent_job = studio_index_service.get_infographic_job(project_id, parent_job_id)
            if not parent_job:
                return jsonify({
                    'success': False,
                    'error': 'Parent job not found'
                }), 404
            previous_image_prompt = parent_job.get("image_prompt")
            if not previous_image_prompt:
                return jsonify({
                    'success': False,
                    'error': 'Parent job has no image prompt to edit'
                }), 400
            # Inherit source_id from parent if not provided
            if not source_id:
                source_id = parent_job.get("source_id", "")

        # Check if Gemini is configured
        if not imagen_service.is_configured():
            return jsonify({
                'success': False,
                'error': 'Gemini API key not configured. Please add it in Admin Settings.'
            }), 400

        # Look up source if provided, otherwise use "Chat Context"
        source_name = 'Chat Context'
        if source_id:
            source = source_index_service.get_source_from_index(project_id, source_id)
            if not source:
                return jsonify({
                    'success': False,
                    'error': f'Source not found: {source_id}'
                }), 404
            source_name = source.get('name', 'Unknown')

        # Create job record
        job_id = str(uuid.uuid4())
        studio_index_service.create_infographic_job(
            project_id=project_id,
            job_id=job_id,
            source_id=source_id,
            source_name=source_name,
            direction=direction,
            parent_job_id=parent_job_id,
            edit_instructions=edit_instructions
        )

        # Resolve brand logo for image generation
        logo_image_bytes, logo_mime_type = resolve_logo(data, project_id)

        # Submit background task
        task_service.submit_task(
            task_type="infographic",
            target_id=job_id,
            callable_func=studio_index_service.with_failure_guard(infographic_service.generate_infographic),
            project_id=project_id,
            source_id=source_id,
            job_id=job_id,
            direction=direction,
            logo_image_bytes=logo_image_bytes,
            logo_mime_type=logo_mime_type,
            user_id=g.user_id,
            edit_instructions=edit_instructions,
            previous_image_prompt=previous_image_prompt
        )

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Infographic generation started',
            'source_name': source_name
        }), 202  # 202 Accepted - processing started

    except Exception as e:
        current_app.logger.error(f"Error starting infographic generation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start infographic generation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/infographic-jobs/<job_id>', methods=['GET'])
def get_infographic_job_status(project_id: str, job_id: str):
    """
    Get the status of an infographic generation job.

    Response:
        - success: Boolean
        - job: Job record with status, progress, image (when ready)
    """
    try:
        job = studio_index_service.get_infographic_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Job not found: {job_id}'
            }), 404

        return jsonify({
            'success': True,
            'job': job
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting infographic job status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get job status: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/infographic-jobs', methods=['GET'])
def list_infographic_jobs(project_id: str):
    """
    List all infographic jobs for a project.

    Query Parameters:
        - source_id: Optional filter by source

    Response:
        - success: Boolean
        - jobs: List of job records
    """
    try:
        source_id = request.args.get('source_id')
        jobs = studio_index_service.list_infographic_jobs(project_id, source_id)

        # Filter out orphaned failed-edit jobs (error + parent_job_id)
        clean_jobs = [
            job for job in jobs
            if not (job.get("status") == "error" and job.get("parent_job_id"))
        ]

        return jsonify({
            'success': True,
            'jobs': clean_jobs,
            'count': len(clean_jobs)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error listing infographic jobs: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list jobs: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/infographic-jobs/<job_id>', methods=['DELETE'])
def delete_infographic_job(project_id: str, job_id: str):
    """
    Delete an infographic job and its files from Supabase Storage.

    Response:
        - Success status
    """
    try:
        job = studio_index_service.get_infographic_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Infographic job {job_id} not found'
            }), 404

        # Delete all files for this job from Supabase Storage
        storage_service.delete_studio_job_files(project_id, "infographics", job_id)

        # Delete job from index
        studio_index_service.delete_infographic_job(project_id, job_id)

        return jsonify({
            'success': True,
            'message': f'Infographic job {job_id} deleted'
        })

    except Exception as e:
        current_app.logger.error(f"Error deleting infographic job: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to delete infographic job: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/infographics/<job_id>/<filename>', methods=['GET'])
def get_infographic_file(project_id: str, job_id: str, filename: str):
    """
    Serve an infographic image file from Supabase Storage.

    Response:
        - Image file (png/jpg) with appropriate headers
    """
    try:
        data = storage_service.download_studio_binary(
            project_id, "infographics", job_id, filename
        )

        if not data:
            return jsonify({
                'success': False,
                'error': f'Infographic not found: {filename}'
            }), 404

        mimetype = 'image/png' if filename.endswith('.png') else 'image/jpeg'

        return send_file(io.BytesIO(data), mimetype=mimetype, as_attachment=False)

    except Exception as e:
        current_app.logger.error(f"Error serving infographic file: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to serve infographic file: {str(e)}'
        }), 500
