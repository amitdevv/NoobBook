"""
Presentation Generator endpoints - AI-generated PowerPoint presentations.

Educational Note: Presentation generation demonstrates HTML-to-PPTX workflow:
1. presentation_agent generates HTML slides with Tailwind CSS
2. Playwright captures screenshots at 1920x1080
3. python-pptx stitches screenshots into a PPTX file

Agent Architecture:
- Uses presentation_agent_executor for orchestration
- Agent has tools for planning, styling, and slide creation
- Sequential slide generation for design consistency
- Export pipeline: HTML -> PNG -> PPTX

Output Structure:
- slides/base-styles.css (brand colors/fonts)
- slides/slide_01.html, slide_02.html, ... (HTML slides)
- screenshots/slide_01.png, slide_02.png, ... (captured screenshots)
- Presentation.pptx (final output)

Routes:
- POST /projects/<id>/studio/presentation                      - Start generation
- GET  /projects/<id>/studio/presentation-jobs/<id>            - Job status
- GET  /projects/<id>/studio/presentation-jobs                 - List jobs
- GET  /projects/<id>/studio/presentations/<id>/slides/<file>  - Serve slide HTML
- GET  /projects/<id>/studio/presentations/<id>/preview        - Preview slide
- GET  /projects/<id>/studio/presentations/<id>/download       - Download PPTX
"""
import io
import zipfile
from flask import jsonify, request, current_app, send_file, Response
from app.api.studio import studio_bp
from app.services.studio_services import studio_index_service
from app.services.integrations.supabase import storage_service


@studio_bp.route('/projects/<project_id>/studio/presentation', methods=['POST'])
def generate_presentation(project_id: str):
    """
    Start presentation generation (background task).

    Request body:
        {
            "source_id": "source-uuid",
            "direction": "optional user direction/preferences"
        }

    Returns:
        202 Accepted with job_id for polling
    """
    from app.services.tool_executors import presentation_agent_executor

    try:
        data = request.get_json()
        source_id = data.get('source_id')

        if not source_id:
            return jsonify({
                'success': False,
                'error': 'source_id is required'
            }), 400

        direction = data.get('direction', '')

        # Execute presentation generation (background task)
        result = presentation_agent_executor.execute(
            project_id=project_id,
            source_id=source_id,
            direction=direction
        )

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result), 202  # Accepted

    except Exception as e:
        current_app.logger.error(f"Error starting presentation generation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start presentation generation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/presentation-jobs/<job_id>', methods=['GET'])
def get_presentation_job_status(project_id: str, job_id: str):
    """
    Get status of a presentation generation job.

    Returns:
        Job object with current status, progress, and results if complete
    """
    try:
        job = studio_index_service.get_presentation_job(project_id, job_id)

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
        current_app.logger.error(f"Error getting presentation job status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get job status: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/presentation-jobs', methods=['GET'])
def list_presentation_jobs(project_id: str):
    """
    List all presentation jobs for a project, optionally filtered by source.

    Query params:
        source_id (optional): Filter by source ID

    Returns:
        List of presentation jobs sorted by created_at descending
    """
    try:
        source_id = request.args.get('source_id')
        jobs = studio_index_service.list_presentation_jobs(project_id, source_id)

        return jsonify({
            'success': True,
            'jobs': jobs
        })

    except Exception as e:
        current_app.logger.error(f"Error listing presentation jobs: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list jobs: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/presentations/<job_id>/slides/<path:filename>', methods=['GET'])
def get_presentation_slide(project_id: str, job_id: str, filename: str):
    """
    Serve a slide file (HTML or CSS).

    Supports:
        - HTML slides: slide_01.html, slide_02.html, etc.
        - Stylesheets: base-styles.css
    """
    try:
        # Determine MIME type
        mime_type = 'text/html'
        if filename.endswith('.css'):
            mime_type = 'text/css'

        # Download from Supabase Storage (files stored under slides/ subfolder)
        content = storage_service.download_studio_file(
            project_id, "presentations", job_id, f"slides/{filename}"
        )
        if content is None:
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404

        return Response(content, mimetype=mime_type)

    except Exception as e:
        current_app.logger.error(f"Error serving slide file: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to serve file: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/presentations/<job_id>/screenshots/<path:filename>', methods=['GET'])
def get_presentation_screenshot(project_id: str, job_id: str, filename: str):
    """
    Serve a screenshot image file (PNG).

    Educational Note: Screenshots are captured by Playwright at 1920x1080
    and used to create the PPTX. They provide a reliable preview.
    """
    try:
        # Download from Supabase Storage (screenshots stored under screenshots/ subfolder)
        file_data = storage_service.download_studio_binary(
            project_id, "presentations", job_id, f"screenshots/{filename}"
        )
        if file_data is None:
            return jsonify({
                'success': False,
                'error': 'Screenshot not found'
            }), 404

        return send_file(io.BytesIO(file_data), mimetype='image/png', as_attachment=False)

    except Exception as e:
        current_app.logger.error(f"Error serving screenshot file: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to serve screenshot: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/presentations/<job_id>/preview', methods=['GET'])
def preview_presentation(project_id: str, job_id: str):
    """
    Preview presentation by returning slide info and first slide.

    Query params:
        slide (optional): Slide number to preview (default: 1)

    Returns:
        JSON with slide info and file URL for iframe viewing
    """
    try:
        job = studio_index_service.get_presentation_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404

        slide_files = job.get('slide_files', [])
        if not slide_files:
            return jsonify({
                'success': False,
                'error': 'No slides available'
            }), 404

        # Get requested slide number (1-indexed)
        slide_num = request.args.get('slide', 1, type=int)
        slide_num = max(1, min(slide_num, len(slide_files)))

        slide_file = slide_files[slide_num - 1]
        slide_url = f"/api/v1/projects/{project_id}/studio/presentations/{job_id}/slides/{slide_file}"

        return jsonify({
            'success': True,
            'total_slides': len(slide_files),
            'current_slide': slide_num,
            'slide_file': slide_file,
            'slide_url': slide_url,
            'presentation_title': job.get('presentation_title', 'Presentation'),
            'export_status': job.get('export_status'),
            'pptx_available': job.get('pptx_file') is not None
        })

    except Exception as e:
        current_app.logger.error(f"Error previewing presentation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to preview presentation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/presentations/<job_id>/download', methods=['GET'])
def download_presentation(project_id: str, job_id: str):
    """
    Download presentation as PPTX file.

    Query params:
        format (optional): 'pptx' (default) or 'zip' (includes HTML source)

    Returns:
        PPTX file or ZIP file with all assets
    """
    try:
        # Get job info
        job = studio_index_service.get_presentation_job(project_id, job_id)
        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404

        download_format = request.args.get('format', 'pptx')

        if download_format == 'pptx':
            # Download PPTX file from Supabase Storage
            pptx_filename = job.get('pptx_file')
            if not pptx_filename:
                return jsonify({
                    'success': False,
                    'error': 'PPTX file not ready yet. Export may still be processing.'
                }), 400

            pptx_data = storage_service.download_studio_binary(
                project_id, "presentations", job_id, pptx_filename
            )
            if pptx_data is None:
                return jsonify({
                    'success': False,
                    'error': 'PPTX file not found'
                }), 404

            download_name = job.get('pptx_filename', 'Presentation.pptx')

            return send_file(
                io.BytesIO(pptx_data),
                mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
                as_attachment=True,
                download_name=download_name
            )

        elif download_format == 'zip':
            # Download as ZIP with all source files from Supabase Storage
            title = job.get('presentation_title', 'Presentation')
            safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
            if not safe_title:
                safe_title = "Presentation"
            zip_filename = f"{safe_title}_source.zip"

            # Create ZIP in memory from Supabase Storage
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add slide HTML files and base-styles.css
                slide_files = job.get('slide_files', [])
                for slide_file in slide_files:
                    content = storage_service.download_studio_file(
                        project_id, "presentations", job_id, f"slides/{slide_file}"
                    )
                    if content:
                        zip_file.writestr(f"slides/{slide_file}", content)

                # Add base-styles.css
                css_content = storage_service.download_studio_file(
                    project_id, "presentations", job_id, "slides/base-styles.css"
                )
                if css_content:
                    zip_file.writestr("slides/base-styles.css", css_content)

                # Add screenshots
                screenshots = job.get('screenshots', [])
                for screenshot_info in screenshots:
                    screenshot_name = screenshot_info.get('filename', '')
                    if not screenshot_name:
                        # Extract filename from path if stored that way
                        path = screenshot_info.get('path', '')
                        if path:
                            screenshot_name = path.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
                    if screenshot_name:
                        img_data = storage_service.download_studio_binary(
                            project_id, "presentations", job_id, f"screenshots/{screenshot_name}"
                        )
                        if img_data:
                            zip_file.writestr(f"screenshots/{screenshot_name}", img_data)

                # Add PPTX file
                pptx_filename = job.get('pptx_file')
                if pptx_filename:
                    pptx_data = storage_service.download_studio_binary(
                        project_id, "presentations", job_id, pptx_filename
                    )
                    if pptx_data:
                        zip_file.writestr(pptx_filename, pptx_data)

            zip_buffer.seek(0)

            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name=zip_filename
            )

        else:
            return jsonify({
                'success': False,
                'error': f'Invalid format: {download_format}. Use "pptx" or "zip".'
            }), 400

    except Exception as e:
        current_app.logger.error(f"Error downloading presentation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to download presentation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/presentations/<job_id>', methods=['DELETE'])
def delete_presentation(project_id: str, job_id: str):
    """
    Delete a presentation and its files.

    Returns:
        Success status
    """
    try:
        # Get job to verify it exists
        job = studio_index_service.get_presentation_job(project_id, job_id)
        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404

        # Delete files from Supabase Storage
        storage_service.delete_studio_job_files(project_id, "presentations", job_id)

        # Delete from index
        deleted = studio_index_service.delete_presentation_job(project_id, job_id)

        return jsonify({
            'success': deleted,
            'message': 'Presentation deleted' if deleted else 'Failed to delete from index'
        })

    except Exception as e:
        current_app.logger.error(f"Error deleting presentation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to delete presentation: {str(e)}'
        }), 500
