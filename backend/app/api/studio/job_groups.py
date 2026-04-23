"""
Grouped Studio Jobs endpoint.

Educational Note: Studio used to bootstrap by having every section hit its own
list endpoint on mount. This route lets the frontend hydrate once and fan the
results back out locally.
"""

from flask import jsonify, current_app

from app.api.studio import studio_bp
from app.services.studio_services import studio_index_service


@studio_bp.route('/projects/<project_id>/studio/job-groups', methods=['GET'])
def list_grouped_studio_jobs(project_id: str):
    """List all studio jobs for a project, grouped by job_type."""
    try:
        jobs_by_type = studio_index_service.list_jobs_grouped(project_id)
        return jsonify({
            'success': True,
            'jobs_by_type': jobs_by_type,
            'count': sum(len(jobs) for jobs in jobs_by_type.values()),
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error listing grouped studio jobs: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list grouped studio jobs: {str(e)}'
        }), 500
