"""
Chats API Blueprint.

Educational Note: This blueprint handles all chat CRUD operations.
Chats are containers for conversations - they hold messages but don't
process AI responses themselves (that's the messages blueprint's job).
"""
from flask import Blueprint, request

# Create blueprint with url_prefix for all chat routes
chats_bp = Blueprint('chats', __name__)


# Verify project ownership for all chat routes
from app.utils.auth_middleware import verify_project_access  # noqa: E402

@chats_bp.before_request
def check_project_access():
    project_id = request.view_args.get('project_id') if request.view_args else None
    if project_id:
        denied = verify_project_access(project_id)
        if denied:
            return denied


# Import routes to register them with the blueprint
from app.api.chats import routes  # noqa: F401
