"""
Website Generator endpoints - AI-generated multi-page websites.

Educational Note: Website generation demonstrates complex agent workflows:
1. website_agent_executor orchestrates the entire process
2. Claude generates HTML, CSS, and JavaScript
3. Gemini generates images for the site
4. Complete package: multiple pages + assets

Agent Architecture:
- Uses website_agent_executor for orchestration
- Agent has tools for page creation, styling, scripting
- Multi-page sites with navigation
- Responsive design patterns

Output Structure:
- index.html (main page)
- Additional pages (about.html, etc.)
- styles.css (stylesheet)
- script.js (JavaScript)
- assets/ folder for images
- All served via Flask endpoints

Routes:
- POST /projects/<id>/studio/website                        - Start generation
- GET  /projects/<id>/studio/website-jobs/<id>              - Job status
- GET  /projects/<id>/studio/website-jobs                   - List jobs
- GET  /projects/<id>/studio/websites/<id>/<path:file>      - Serve files
- GET  /projects/<id>/studio/websites/<id>/preview          - Preview site
- GET  /projects/<id>/studio/websites/<id>/download         - Download ZIP
"""
import io
import re
import zipfile
from flask import jsonify, request, current_app, send_file, Response
from app.api.studio import studio_bp
from app.services.studio_services import studio_index_service
from app.services.integrations.supabase import storage_service


@studio_bp.route('/projects/<project_id>/studio/website', methods=['POST'])
def generate_website(project_id: str):
    """
    Start website generation (background task).

    Request body:
        {
            "source_id": "source-uuid",
            "direction": "optional user direction/preferences"
        }

    Returns:
        202 Accepted with job_id for polling
    """
    from app.services.tool_executors import website_agent_executor

    try:
        data = request.get_json()
        source_id = data.get('source_id')

        if not source_id:
            return jsonify({
                'success': False,
                'error': 'source_id is required'
            }), 400

        direction = data.get('direction', '')

        # Execute website generation (background task)
        result = website_agent_executor.execute(
            project_id=project_id,
            source_id=source_id,
            direction=direction
        )

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result), 202  # Accepted

    except Exception as e:
        current_app.logger.error(f"Error starting website generation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start website generation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/website-jobs/<job_id>', methods=['GET'])
def get_website_job_status(project_id: str, job_id: str):
    """
    Get status of a website generation job.

    Returns:
        Job object with current status, progress, and results if complete
    """
    try:
        job = studio_index_service.get_website_job(project_id, job_id)

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
        current_app.logger.error(f"Error getting website job status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get job status: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/website-jobs', methods=['GET'])
def list_website_jobs(project_id: str):
    """
    List all website jobs for a project, optionally filtered by source.

    Query params:
        source_id (optional): Filter by source ID

    Returns:
        List of website jobs sorted by created_at descending
    """
    try:
        source_id = request.args.get('source_id')
        jobs = studio_index_service.list_website_jobs(project_id, source_id)

        return jsonify({
            'success': True,
            'jobs': jobs
        })

    except Exception as e:
        current_app.logger.error(f"Error listing website jobs: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list jobs: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/websites/<job_id>/<path:filename>', methods=['GET'])
def get_website_file(project_id: str, job_id: str, filename: str):
    """
    Serve a website file (HTML, CSS, JS, or image asset).

    Supports:
        - HTML pages: index.html, about.html, etc.
        - Stylesheets: styles.css
        - Scripts: script.js
        - Assets: assets/image_1.png, etc.
    """
    try:
        # Determine MIME type
        mime_type = 'text/html'
        if filename.endswith('.css'):
            mime_type = 'text/css'
        elif filename.endswith('.js'):
            mime_type = 'application/javascript'
        elif filename.endswith('.png'):
            mime_type = 'image/png'
        elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
            mime_type = 'image/jpeg'
        elif filename.endswith('.gif'):
            mime_type = 'image/gif'
        elif filename.endswith('.svg'):
            mime_type = 'image/svg+xml'
        elif filename.endswith('.webp'):
            mime_type = 'image/webp'

        # Binary files (images)
        is_binary = mime_type.startswith('image/')
        if is_binary:
            file_data = storage_service.download_studio_binary(
                project_id, "websites", job_id, filename
            )
            if file_data is None:
                return jsonify({'success': False, 'error': 'File not found'}), 404
            return send_file(io.BytesIO(file_data), mimetype=mime_type, as_attachment=False)

        # Text files (HTML, CSS, JS)
        content = storage_service.download_studio_file(
            project_id, "websites", job_id, filename
        )
        if content is None:
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # For CSS files, inject auth token into url() references so images load.
        # Educational Note: CSS url() references (e.g. background-image) trigger
        # separate browser requests that don't carry the parent page's query params.
        token = request.args.get('token', '')
        if mime_type == 'text/css' and token:
            def _add_token_to_css_url(match: re.Match) -> str:
                prefix = match.group(1)
                url = match.group(2)
                suffix = match.group(3)
                sep = '&' if '?' in url else '?'
                return f'{prefix}{url}{sep}token={token}{suffix}'

            content = re.sub(
                r"""(url\(["']?)(?!https?://|//|data:)([^"')\s]+)(["']?\))""",
                _add_token_to_css_url,
                content
            )

        return Response(content, mimetype=mime_type)

    except Exception as e:
        current_app.logger.error(f"Error serving website file: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to serve file: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/websites/<job_id>/preview', methods=['GET'])
def preview_website(project_id: str, job_id: str):
    """
    Preview website by serving index.html with auth tokens injected.

    Educational Note: The iframe can't pass Authorization headers for sub-resource
    requests (CSS, JS, images). We inject ?token= into local resource URLs in the
    HTML so the browser passes the JWT when fetching these files. The original
    files on disk stay clean for download/export.
    """
    try:
        # Download index.html from Supabase Storage
        html_content = storage_service.download_studio_file(
            project_id, "websites", job_id, "index.html"
        )
        if html_content is None:
            return jsonify({
                'success': False,
                'error': 'Website not ready yet or index.html not found'
            }), 404

        # Inject auth token into local resource URLs (CSS, JS, images)
        token = request.args.get('token', '')
        if token:
            def _add_token(match: re.Match) -> str:
                attr = match.group(1)   # src or href
                url = match.group(2)
                sep = '&' if '?' in url else '?'
                return f'{attr}="{url}{sep}token={token}"'

            # Match src="..." and href="..." but skip external URLs
            html_content = re.sub(
                r'(src|href)="(?!https?://|//|data:|#|mailto:)([^"]+)"',
                _add_token,
                html_content
            )

        return Response(html_content, mimetype='text/html')

    except Exception as e:
        current_app.logger.error(f"Error previewing website: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to preview website: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/websites/<job_id>/download', methods=['GET'])
def download_website(project_id: str, job_id: str):
    """
    Download website as ZIP file containing all files.

    Returns:
        ZIP file with all HTML pages, CSS, JS, and image assets
    """
    try:
        # Get job info
        job = studio_index_service.get_website_job(project_id, job_id)
        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404

        if job['status'] != 'ready':
            return jsonify({
                'success': False,
                'error': 'Website not ready yet'
            }), 400

        site_name = job.get('site_name', 'Website')
        zip_filename = f"{site_name.replace(' ', '_')}.zip"

        # Create ZIP in memory from Supabase Storage
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add text files (HTML, CSS, JS) from job metadata
            for fname in job.get('files', []):
                content = storage_service.download_studio_file(
                    project_id, "websites", job_id, fname
                )
                if content:
                    zip_file.writestr(fname, content)

            # Add image assets
            for image_info in job.get('images', []):
                img_filename = image_info.get('filename')
                if img_filename:
                    img_data = storage_service.download_studio_binary(
                        project_id, "websites", job_id, f"assets/{img_filename}"
                    )
                    if img_data:
                        zip_file.writestr(f"assets/{img_filename}", img_data)

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )

    except Exception as e:
        current_app.logger.error(f"Error downloading website: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to download website: {str(e)}'
        }), 500
