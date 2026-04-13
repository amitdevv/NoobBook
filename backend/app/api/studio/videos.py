"""
Video Generation endpoints - AI-generated video clips.

Educational Note: Videos demonstrate advanced generative AI:
1. video_executor orchestrates the generation
2. Claude analyzes source and creates video prompts
3. Google Veo generates the actual video
4. Videos are short clips (5-8 seconds)

Video Generation Pattern:
- Google Veo API for video generation
- Supports multiple aspect ratios (16:9, 16:10)
- Can generate multiple videos per request
- Videos are stored as MP4 files

Use Cases:
- Product demonstrations from descriptions
- Concept visualizations from documents
- Marketing video snippets from brand materials
- Educational animations from course content

Routes:
- POST /projects/<id>/studio/videos                         - Start generation
- GET  /projects/<id>/studio/videos/<id>                    - Job status (also works with GET /videos)
- GET  /projects/<id>/studio/videos                         - List jobs
- GET  /projects/<id>/studio/videos/<id>/preview/<file>     - Preview video
- GET  /projects/<id>/studio/videos/<id>/download/<file>    - Download video
"""
import io
from flask import jsonify, request, current_app, send_file
from app.api.studio import studio_bp
from app.services.studio_services import studio_index_service
from app.services.integrations.supabase import storage_service
from app.services.auth import require_permission


@studio_bp.route('/projects/<project_id>/studio/videos', methods=['POST'])
@require_permission("studio", "videos")
def generate_video(project_id: str):
    """
    Start video generation as a background task.

    Request Body:
        - source_id: UUID of the source (required)
        - direction: Optional guidance for video generation
        - aspect_ratio: "16:9" or "16:10" (default: "16:9")
        - duration_seconds: 5-8 seconds (default: 8)
        - number_of_videos: 1-4 (default: 1)
        - parent_job_id: UUID of the parent video job to edit (optional, for edits)
        - edit_instructions: Instructions for editing the parent video (optional, for edits)

    Response:
        - success: Boolean
        - job_id: UUID for status polling
        - status: "processing"
        - message: Status message
    """
    try:
        from app.services.tool_executors.video_executor import video_executor

        data = request.get_json()
        source_id = data.get("source_id")
        direction = data.get("direction", "")
        aspect_ratio = data.get("aspect_ratio", "16:9")
        duration_seconds = data.get("duration_seconds", 8)
        number_of_videos = data.get("number_of_videos", 1)

        # Edit mode: load parent job's generated prompt as context for refinement
        parent_job_id = data.get("parent_job_id")
        edit_instructions = data.get("edit_instructions")
        previous_prompt = None

        if parent_job_id:
            # Clean up any previously failed edit jobs for this parent
            try:
                all_jobs = studio_index_service.list_video_jobs(project_id)
                for job in all_jobs:
                    if (job.get("status") == "error"
                            and job.get("parent_job_id") == parent_job_id):
                        studio_index_service.delete_video_job(project_id, job["id"])
            except Exception:
                pass  # Non-critical cleanup

            parent_job = studio_index_service.get_video_job(project_id, parent_job_id)
            if not parent_job:
                return jsonify({
                    'success': False,
                    'error': 'Parent job not found'
                }), 404
            previous_prompt = parent_job.get("generated_prompt")
            if not previous_prompt:
                return jsonify({
                    'success': False,
                    'error': 'Parent job has no generated prompt to edit'
                }), 400
            # Inherit source_id from parent if not provided
            if not source_id:
                source_id = parent_job.get("source_id")

        if not source_id:
            return jsonify({
                'success': False,
                'error': 'source_id is required'
            }), 400

        # Validate parameters
        if aspect_ratio not in ["16:9", "16:10"]:
            return jsonify({
                'success': False,
                'error': 'aspect_ratio must be "16:9" or "16:10"'
            }), 400

        if not (5 <= duration_seconds <= 8):
            return jsonify({
                'success': False,
                'error': 'duration_seconds must be between 5 and 8'
            }), 400

        if not (1 <= number_of_videos <= 4):
            return jsonify({
                'success': False,
                'error': 'number_of_videos must be between 1 and 4'
            }), 400

        # Execute video generation
        result = video_executor.execute(
            project_id=project_id,
            source_id=source_id,
            direction=direction,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
            number_of_videos=number_of_videos,
            edit_instructions=edit_instructions,
            previous_prompt=previous_prompt,
            parent_job_id=parent_job_id
        )

        if not result.get("success"):
            return jsonify(result), 400

        return jsonify(result), 202

    except Exception as e:
        current_app.logger.error(f"Error starting video generation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start video generation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/videos/<job_id>', methods=['GET'])
def get_video_job_status(project_id: str, job_id: str):
    """
    Get video generation job status.

    Response:
        - success: Boolean
        - job: Video job record with status and videos
    """
    try:
        job = studio_index_service.get_video_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404

        return jsonify({
            'success': True,
            'job': job
        })

    except Exception as e:
        current_app.logger.error(f"Error getting video job status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get job status: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/videos', methods=['GET'])
def list_video_jobs(project_id: str):
    """
    List all video jobs for a project.

    Query Parameters:
        - source_id: Optional filter by source

    Response:
        - success: Boolean
        - jobs: List of video jobs
    """
    try:
        source_id = request.args.get('source_id')
        jobs = studio_index_service.list_video_jobs(project_id, source_id)

        # Filter out orphaned failed-edit jobs (error + parent_job_id)
        clean_jobs = [
            job for job in jobs
            if not (job.get("status") == "error" and job.get("parent_job_id"))
        ]

        return jsonify({
            'success': True,
            'jobs': clean_jobs
        })

    except Exception as e:
        current_app.logger.error(f"Error listing video jobs: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list video jobs: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/videos/<job_id>/preview/<filename>', methods=['GET'])
def preview_video(project_id: str, job_id: str, filename: str):
    """
    Preview a generated video file from Supabase Storage.

    Returns the video file for playback in browser.
    """
    try:
        data = storage_service.download_studio_binary(
            project_id, "videos", job_id, filename
        )

        if not data:
            return jsonify({
                'success': False,
                'error': 'Video file not found'
            }), 404

        return send_file(io.BytesIO(data), mimetype='video/mp4', as_attachment=False)

    except Exception as e:
        current_app.logger.error(f"Error serving video preview: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to serve video: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/videos/<job_id>/download/<filename>', methods=['GET'])
def download_video(project_id: str, job_id: str, filename: str):
    """
    Download a generated video file from Supabase Storage.

    Returns the video file as an attachment.
    """
    try:
        data = storage_service.download_studio_binary(
            project_id, "videos", job_id, filename
        )

        if not data:
            return jsonify({
                'success': False,
                'error': 'Video file not found'
            }), 404

        return send_file(
            io.BytesIO(data),
            mimetype='video/mp4',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        current_app.logger.error(f"Error downloading video: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to download video: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/videos/<job_id>', methods=['DELETE'])
def delete_video_job(project_id: str, job_id: str):
    """
    Delete a video job and its files from Supabase Storage.

    Response:
        - Success status
    """
    try:
        job = studio_index_service.get_video_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Video job {job_id} not found'
            }), 404

        # Delete all files for this job from Supabase Storage
        storage_service.delete_studio_job_files(project_id, "videos", job_id)

        # Delete job from index
        studio_index_service.delete_video_job(project_id, job_id)

        return jsonify({
            'success': True,
            'message': f'Video job {job_id} deleted'
        })

    except Exception as e:
        current_app.logger.error(f"Error deleting video job: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to delete video job: {str(e)}'
        }), 500
