"""
Social Post endpoints - Platform-specific social media content.

Educational Note: Social posts demonstrate multi-platform content generation:
1. Claude generates platform-optimized copy
2. Gemini Imagen creates accompanying images
3. Different formats for LinkedIn, Facebook/Instagram, Twitter/X

Platform Optimization:
- LinkedIn: Professional tone, longer format, business insights
- Facebook/Instagram: Engaging visuals, hashtags, call-to-action
- Twitter/X: Concise text, thread-ready, emoji usage

Multi-Modal Pipeline:
1. Analyze topic/source content
2. Generate copy for each platform
3. Create visual descriptions for images
4. Generate images with Gemini Imagen
5. Upload to Supabase Storage
6. Return public URLs

Routes:
- POST /projects/<id>/studio/social-posts                    - Start generation
- GET  /projects/<id>/studio/social-post-jobs/<id>           - Job status
- GET  /projects/<id>/studio/social-post-jobs                - List jobs
- GET  /projects/<id>/studio/social/<job_id>/<file>          - Serve image file (from Supabase)
"""
import io
import uuid
from flask import g, jsonify, request, current_app, send_file
from app.api.studio import studio_bp
from app.api.studio.logo_utils import resolve_logo
from app.services.studio_services import studio_index_service
from app.services.studio_services.social_posts_service import social_posts_service
from app.services.integrations.google.imagen_service import imagen_service
from app.services.integrations.supabase import storage_service
from app.services.background_services.task_service import task_service


@studio_bp.route('/projects/<project_id>/studio/social-posts', methods=['POST'])
def generate_social_posts(project_id: str):
    """
    Start social post generation as a background task.

    Educational Note: Social posts are generated with platform-specific images
    and copy for LinkedIn, Facebook/Instagram, and Twitter/X.

    Request Body:
        - topic: Topic/content to create posts about (required)
        - direction: Optional guidance for the style/focus
        - platforms: Optional list of platforms to generate for (default: all 3)
                     Valid values: 'linkedin', 'instagram', 'twitter'
        - parent_job_id: Optional parent job ID for iterative editing
        - edit_instructions: Optional edit instructions (requires parent_job_id)

    Response:
        - success: Boolean
        - job_id: ID for polling status
        - message: Status message
    """
    try:
        data = request.get_json() or {}

        # Edit mode: load parent job's posts as context for refinement
        parent_job_id = data.get("parent_job_id")
        edit_instructions = data.get("edit_instructions")
        previous_posts = None
        parent_job = None

        if parent_job_id:
            # Clean up any previously failed edit jobs for this parent
            try:
                all_jobs = studio_index_service.list_social_post_jobs(project_id)
                for job in all_jobs:
                    if (job.get("status") == "error"
                            and job.get("parent_job_id") == parent_job_id):
                        studio_index_service.delete_social_post_job(project_id, job["id"])
            except Exception:
                pass  # Non-critical cleanup

            parent_job = studio_index_service.get_social_post_job(project_id, parent_job_id)
            if not parent_job:
                return jsonify({
                    'success': False,
                    'error': 'Parent job not found'
                }), 404
            previous_posts = parent_job.get("posts")
            if not previous_posts:
                return jsonify({
                    'success': False,
                    'error': 'Parent job has no posts to edit'
                }), 400

        topic = data.get('topic')
        # Inherit topic from parent if not provided (edit mode)
        if not topic and parent_job_id and parent_job:
            topic = parent_job.get("topic", "Topic")
        if not topic:
            return jsonify({
                'success': False,
                'error': 'topic is required'
            }), 400

        direction = data.get('direction', 'Create engaging social media posts for this topic.')

        # Validate platforms parameter — inherit from parent in edit mode
        valid_platforms = {'linkedin', 'instagram', 'twitter'}
        default_platforms = parent_job.get("platforms", list(valid_platforms)) if (parent_job_id and parent_job) else list(valid_platforms)
        platforms = data.get('platforms', default_platforms)
        platforms = [p.lower() for p in platforms if p.lower() in valid_platforms]
        if not platforms:
            return jsonify({
                'success': False,
                'error': 'At least one valid platform is required (linkedin, instagram, twitter)'
            }), 400

        # Check if Gemini is configured
        if not imagen_service.is_configured():
            return jsonify({
                'success': False,
                'error': 'Gemini API key not configured. Please add it in Admin Settings.'
            }), 400

        # Resolve logo image bytes (brand icon or image source)
        logo_image_bytes, logo_mime_type = resolve_logo(data, project_id)

        # Create job record
        job_id = str(uuid.uuid4())
        studio_index_service.create_social_post_job(
            project_id=project_id,
            job_id=job_id,
            topic=topic,
            direction=direction,
            platforms=platforms,
            parent_job_id=parent_job_id,
            edit_instructions=edit_instructions
        )

        # Submit background task
        task_service.submit_task(
            task_type="social_posts",
            target_id=job_id,
            callable_func=social_posts_service.generate_social_posts,
            project_id=project_id,
            job_id=job_id,
            topic=topic,
            direction=direction,
            platforms=platforms,
            logo_image_bytes=logo_image_bytes,
            logo_mime_type=logo_mime_type,
            user_id=g.user_id,
            edit_instructions=edit_instructions,
            previous_posts=previous_posts
        )

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Social post generation started',
            'topic': topic
        }), 202  # 202 Accepted - processing started

    except Exception as e:
        current_app.logger.error(f"Error starting social post generation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start social post generation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/social-post-jobs/<job_id>', methods=['GET'])
def get_social_post_job_status(project_id: str, job_id: str):
    """
    Get the status of a social post generation job.

    Response:
        - success: Boolean
        - job: Job record with status, progress, posts (when ready)
    """
    try:
        job = studio_index_service.get_social_post_job(project_id, job_id)

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
        current_app.logger.error(f"Error getting social post job status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get job status: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/social-post-jobs', methods=['GET'])
def list_social_post_jobs(project_id: str):
    """
    List all social post jobs for a project.

    Response:
        - success: Boolean
        - jobs: List of job records
    """
    try:
        jobs = studio_index_service.list_social_post_jobs(project_id)

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
        current_app.logger.error(f"Error listing social post jobs: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list jobs: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/social-post-jobs/<job_id>', methods=['DELETE'])
def delete_social_post_job(project_id: str, job_id: str):
    """
    Delete a social post job and its files from Supabase Storage.

    Response:
        - Success status
    """
    try:
        job = studio_index_service.get_social_post_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Social post job {job_id} not found'
            }), 404

        # Delete all files for this job from Supabase Storage
        storage_service.delete_studio_job_files(project_id, "social_posts", job_id)

        # Delete job from index
        studio_index_service.delete_social_post_job(project_id, job_id)

        return jsonify({
            'success': True,
            'message': f'Social post job {job_id} deleted'
        })

    except Exception as e:
        current_app.logger.error(f"Error deleting social post job: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to delete social post job: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/social/<job_id>/<filename>', methods=['GET'])
def get_social_file(project_id: str, job_id: str, filename: str):
    """
    Serve a social post image file from Supabase Storage.

    Response:
        - Image file (png/jpg) with appropriate headers
    """
    try:
        # Fetch from Supabase Storage
        file_data = storage_service.download_studio_binary(
            project_id=project_id,
            job_type="social_posts",
            job_id=job_id,
            filename=filename
        )

        if file_data is None:
            return jsonify({
                'success': False,
                'error': f'Social image not found: {filename}'
            }), 404

        # Determine mimetype
        mimetype = 'image/png' if filename.endswith('.png') else 'image/jpeg'

        return send_file(
            io.BytesIO(file_data),
            mimetype=mimetype,
            as_attachment=False
        )

    except Exception as e:
        current_app.logger.error(f"Error serving social file: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to serve social file: {str(e)}'
        }), 500
