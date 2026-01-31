"""
Brand API Blueprint.

Educational Note: Brand assets and configuration provide consistent branding
across studio-generated content. This blueprint handles:

Assets (logos, icons, fonts, images):
- GET    /projects/<id>/brand/assets           - List all assets
- POST   /projects/<id>/brand/assets           - Upload new asset (multipart)
- GET    /projects/<id>/brand/assets/<asset_id> - Get asset metadata
- PUT    /projects/<id>/brand/assets/<asset_id> - Update asset metadata
- DELETE /projects/<id>/brand/assets/<asset_id> - Delete asset
- GET    /projects/<id>/brand/assets/<asset_id>/download - Get download URL

Configuration (colors, typography, guidelines):
- GET    /projects/<id>/brand/config           - Get brand config
- PUT    /projects/<id>/brand/config           - Update full config
- PUT    /projects/<id>/brand/config/colors    - Update colors only
- PUT    /projects/<id>/brand/config/typography - Update typography only
- PUT    /projects/<id>/brand/config/guidelines - Update guidelines only
"""
from flask import Blueprint, request

# Create blueprint for brand operations
brand_bp = Blueprint('brand', __name__)


# Verify project ownership for all brand routes
from app.utils.auth_middleware import verify_project_access  # noqa: E402

@brand_bp.before_request
def check_project_access():
    project_id = request.view_args.get('project_id') if request.view_args else None
    if project_id:
        denied = verify_project_access(project_id)
        if denied:
            return denied


# Import routes to register them with the blueprint
from app.api.brand import routes  # noqa: F401
