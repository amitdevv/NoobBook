"""
Brand API Blueprint.

Educational Note: Brand assets and configuration are workspace-level settings
(per-user, not per-project). This provides consistent branding across all
projects' studio-generated content.

Assets (logos, icons, fonts, images):
- GET    /brand/assets           - List all assets
- POST   /brand/assets           - Upload new asset (multipart)
- GET    /brand/assets/<asset_id> - Get asset metadata
- PUT    /brand/assets/<asset_id> - Update asset metadata
- DELETE /brand/assets/<asset_id> - Delete asset
- GET    /brand/assets/<asset_id>/download - Get download URL

Configuration (colors, typography, guidelines):
- GET    /brand/config           - Get brand config
- PUT    /brand/config           - Update full config
- PUT    /brand/config/colors    - Update colors only
- PUT    /brand/config/typography - Update typography only
- PUT    /brand/config/guidelines - Update guidelines only
"""
from flask import Blueprint

# Create blueprint for brand operations
# Auth is handled by the global api_bp.before_request hook (sets g.user_id)
brand_bp = Blueprint('brand', __name__)

# Import routes to register them with the blueprint
from app.api.brand import routes  # noqa: F401
