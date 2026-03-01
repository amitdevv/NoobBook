"""
Email Template endpoints - AI-generated HTML email templates.

Educational Note: Email templates demonstrate agent-based generation:
1. email_agent_executor orchestrates the generation
2. Claude creates HTML structure and content
3. Gemini generates header/banner images
4. Complete package: HTML + images

Agent Pattern:
- Uses email_agent_executor for orchestration
- Agent has tools for HTML generation and image creation
- Multi-step process with intermediate results
- Final output is a complete email template

Output Structure:
- HTML file with inline styles (email-safe)
- Image files for headers/banners
- All files stored in job-specific folder
- ZIP download available for full package

Routes:
- POST /projects/<id>/studio/email-template              - Start generation
- GET  /projects/<id>/studio/email-jobs/<id>             - Job status
- GET  /projects/<id>/studio/email-jobs                  - List jobs
- GET  /projects/<id>/studio/email-templates/<file>      - Serve file
- GET  /projects/<id>/studio/email-templates/<id>/preview  - Preview HTML
- GET  /projects/<id>/studio/email-templates/<id>/download - Download ZIP
"""
import io
import re
import zipfile
from flask import g, jsonify, request, current_app, send_file, Response
from app.api.studio import studio_bp
from app.services.studio_services import studio_index_service
from app.services.tool_executors.email_agent_executor import email_agent_executor
from app.services.integrations.supabase import storage_service


@studio_bp.route('/projects/<project_id>/studio/email-template', methods=['POST'])
def generate_email_template(project_id: str):
    """
    Start email template generation via email agent.

    Request Body:
        - source_id: UUID of the source to generate template from (required)
        - direction: User's direction/guidance (optional)

    Response:
        - 202 Accepted with job_id for polling
    """
    try:
        data = request.get_json()

        # source_id is optional — email can be generated from direction alone
        source_id = data.get('source_id', '')
        direction = data.get('direction', '')

        # Execute via email_agent_executor (creates job and launches agent)
        result = email_agent_executor.execute(
            project_id=project_id,
            source_id=source_id,
            direction=direction,
            user_id=g.user_id
        )

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify({
            'success': True,
            'job_id': result['job_id'],
            'status': result['status'],
            'message': result['message']
        }), 202

    except Exception as e:
        current_app.logger.error(f"Error starting email template generation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start email template generation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/email-jobs/<job_id>', methods=['GET'])
def get_email_job_status(project_id: str, job_id: str):
    """
    Get the status of an email template generation job.

    Response:
        - Job object with status, progress, and generated content
    """
    try:
        job = studio_index_service.get_email_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Email job {job_id} not found'
            }), 404

        return jsonify({
            'success': True,
            'job': job
        })

    except Exception as e:
        current_app.logger.error(f"Error getting email job status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@studio_bp.route('/projects/<project_id>/studio/email-jobs', methods=['GET'])
def list_email_jobs(project_id: str):
    """
    List all email template jobs for a project.

    Query Parameters:
        - source_id: Optional filter by source

    Response:
        - List of email jobs (newest first)
    """
    try:
        source_id = request.args.get('source_id')
        jobs = studio_index_service.list_email_jobs(project_id, source_id)

        return jsonify({
            'success': True,
            'jobs': jobs
        })

    except Exception as e:
        current_app.logger.error(f"Error listing email jobs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@studio_bp.route('/projects/<project_id>/studio/email-templates/<filename>', methods=['GET'])
def get_email_template_file(project_id: str, filename: str):
    """
    Serve an email template file (HTML or image).

    Response:
        - HTML file or image file with appropriate headers
    """
    try:
        # Extract job_id from filename (format: {job_id}.html or {job_id}_image_N.ext or {job_id}_brand_logo.ext)
        # Job ID is the first UUID-length segment before any suffix
        job_id = filename.split('_image_')[0].split('_brand_')[0].split('.')[0]

        # Determine mimetype
        if filename.endswith('.html'):
            mimetype = 'text/html'
        elif filename.endswith('.png'):
            mimetype = 'image/png'
        elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
            mimetype = 'image/jpeg'
        elif filename.endswith('.svg'):
            mimetype = 'image/svg+xml'
        else:
            mimetype = 'application/octet-stream'

        # Text files (HTML)
        if filename.endswith('.html'):
            content = storage_service.download_studio_file(
                project_id, "emails", job_id, filename
            )
            if content is None:
                return jsonify({
                    'success': False,
                    'error': f'File not found: {filename}'
                }), 404
            return Response(content, mimetype=mimetype, headers={'Content-Type': f'{mimetype}; charset=utf-8'})

        # Binary files (images)
        file_data = storage_service.download_studio_binary(
            project_id, "emails", job_id, filename
        )
        if file_data is None:
            return jsonify({
                'success': False,
                'error': f'File not found: {filename}'
            }), 404
        return send_file(io.BytesIO(file_data), mimetype=mimetype, as_attachment=False)

    except Exception as e:
        current_app.logger.error(f"Error serving email template file: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to serve file: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/email-templates/<job_id>/preview', methods=['GET'])
def preview_email_template(project_id: str, job_id: str):
    """
    Serve email template HTML for preview (iframe).

    Educational Note: The iframe can't send Authorization headers for <img> tags
    inside the HTML. We inject ?token= into image src URLs so the browser passes
    the JWT when fetching images. This rewriting only affects the preview — the
    original HTML on disk stays clean for download/export.

    Response:
        - HTML with auth-aware image URLs for rendering in iframe
    """
    try:
        # Get job to find HTML file
        job = studio_index_service.get_email_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Email job {job_id} not found'
            }), 404

        html_file = job.get('html_file')
        if not html_file:
            return jsonify({
                'success': False,
                'error': 'Email template not yet generated'
            }), 404

        # Download from Supabase Storage
        html_content = storage_service.download_studio_file(
            project_id, "emails", job_id, html_file
        )
        if html_content is None:
            return jsonify({
                'success': False,
                'error': f'HTML file not found: {html_file}'
            }), 404

        # Inject auth token into image URLs so <img> tags pass auth.
        # The token comes from the ?token= query param the frontend already sends.
        token = request.args.get('token', '')
        if token:
            # Match image src attributes pointing to our email-templates endpoint
            # e.g. src="/api/v1/projects/.../studio/email-templates/image.png"
            def _add_token(match: re.Match) -> str:
                url = match.group(1)
                separator = '&' if '?' in url else '?'
                return f'src="{url}{separator}token={token}"'

            html_content = re.sub(
                r'src="(/api/v1/projects/[^"]+/studio/email-templates/[^"]+\.(?:png|jpg|jpeg|gif|webp|svg))"',
                _add_token,
                html_content
            )

        return Response(html_content, mimetype='text/html')

    except Exception as e:
        current_app.logger.error(f"Error previewing email template: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to preview template: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/email-templates/<job_id>/download', methods=['GET'])
def download_email_template(project_id: str, job_id: str):
    """
    Download email template as ZIP file (HTML + images).

    Response:
        - ZIP file containing HTML and all images
    """
    try:
        # Get job to find files
        job = studio_index_service.get_email_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Email job {job_id} not found'
            }), 404

        html_file = job.get('html_file')
        if not html_file:
            return jsonify({
                'success': False,
                'error': 'Email template not yet generated'
            }), 404

        # Create ZIP in memory from Supabase Storage
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add HTML file
            html_content = storage_service.download_studio_file(
                project_id, "emails", job_id, html_file
            )
            if html_content:
                zip_file.writestr(html_file, html_content)

            # Add image files
            images = job.get('images', [])
            for image_info in images:
                image_filename = image_info.get('filename')
                if image_filename:
                    image_data = storage_service.download_studio_binary(
                        project_id, "emails", job_id, image_filename
                    )
                    if image_data:
                        zip_file.writestr(image_filename, image_data)

        zip_buffer.seek(0)

        # Generate filename
        template_name = job.get('template_name', 'email_template')
        safe_name = "".join(c for c in template_name if c.isalnum() or c in (' ', '_', '-')).strip()
        zip_filename = f"{safe_name}.zip"

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )

    except Exception as e:
        current_app.logger.error(f"Error downloading email template: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to download template: {str(e)}'
        }), 500
