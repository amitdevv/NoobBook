"""
Brand API endpoints.

Educational Note: These endpoints manage brand assets and configuration
at the workspace (user) level. Brand settings are used by studio agents
to maintain consistent branding across all projects' generated content.

Asset Types:
- logo: Brand logos (SVG, PNG preferred)
- icon: Smaller icons for UI elements
- font: Custom font files (TTF, OTF, WOFF)
- image: Brand imagery (backgrounds, patterns, etc.)

Configuration Sections:
- colors: Color palette (primary, secondary, accent, etc.)
- typography: Font families and sizing
- guidelines: Written brand guidelines (markdown supported)
- best_practices: Dos and don'ts lists
- voice: Brand voice (tone, personality, keywords)
- feature_settings: Per-feature toggles for brand application
"""
import io
import logging
from flask import request, jsonify, g, send_file
from app.api.brand import brand_bp
from app.services.data_services import brand_asset_service, brand_config_service
from app.services.integrations.supabase import storage_service

logger = logging.getLogger(__name__)


# =============================================================================
# BRAND ASSETS ENDPOINTS
# =============================================================================

@brand_bp.route('/brand/assets', methods=['GET'])
def list_assets():
    """
    List all brand assets for the authenticated user.

    Optional Query Parameters:
        type: Filter by asset type (logo, icon, font, image)

    Returns:
        {
            "success": true,
            "assets": [...],
            "count": 5
        }
    """
    try:
        user_id = g.user_id
        asset_type = request.args.get('type')

        if asset_type:
            assets = brand_asset_service.list_assets_by_type(user_id, asset_type)
        else:
            assets = brand_asset_service.list_assets(user_id)

        return jsonify({
            "success": True,
            "assets": assets,
            "count": len(assets)
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@brand_bp.route('/brand/assets', methods=['POST'])
def upload_asset():
    """
    Upload a new brand asset.

    Educational Note: This endpoint uses multipart/form-data for file upload.
    The file is stored in Supabase Storage and metadata in the database.

    Form Data:
        file: The asset file (required)
        name: Display name for the asset (required)
        asset_type: Type of asset - logo, icon, font, image (required)
        description: Optional description
        is_primary: Whether this is the primary asset of its type (default: false)

    Returns:
        {
            "success": true,
            "asset": { ... },
            "message": "Brand asset uploaded successfully"
        }
    """
    try:
        user_id = g.user_id

        # Check for file
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "No file provided"
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "success": False,
                "error": "No file selected"
            }), 400

        # Get form data
        name = request.form.get('name', '').strip()
        asset_type = request.form.get('asset_type', '').strip().lower()
        description = request.form.get('description', '').strip() or None
        is_primary = request.form.get('is_primary', 'false').lower() == 'true'

        # Validate required fields
        if not name:
            return jsonify({
                "success": False,
                "error": "Asset name is required"
            }), 400

        valid_types = ['logo', 'icon', 'font', 'image']
        if asset_type not in valid_types:
            return jsonify({
                "success": False,
                "error": f"Invalid asset type. Must be one of: {', '.join(valid_types)}"
            }), 400

        # Read file data
        file_data = file.read()
        file_name = file.filename
        mime_type = file.content_type or 'application/octet-stream'

        # Create the asset
        asset = brand_asset_service.create_asset(
            user_id=user_id,
            name=name,
            asset_type=asset_type,
            file_name=file_name,
            file_data=file_data,
            mime_type=mime_type,
            description=description,
            is_primary=is_primary
        )

        return jsonify({
            "success": True,
            "asset": asset,
            "message": "Brand asset uploaded successfully"
        }), 201

    except RuntimeError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to upload brand asset: {str(e)}"
        }), 500


@brand_bp.route('/brand/assets/<asset_id>', methods=['GET'])
def get_asset(asset_id: str):
    """
    Get a single brand asset's metadata.

    Returns:
        {
            "success": true,
            "asset": { id, name, asset_type, file_name, ... }
        }
    """
    try:
        user_id = g.user_id
        asset = brand_asset_service.get_asset(user_id, asset_id)

        if not asset:
            return jsonify({
                "success": False,
                "error": "Brand asset not found"
            }), 404

        return jsonify({
            "success": True,
            "asset": asset
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@brand_bp.route('/brand/assets/<asset_id>', methods=['PUT'])
def update_asset(asset_id: str):
    """
    Update a brand asset's metadata (not the file itself).

    Request Body:
        {
            "name": "New Name",           # optional
            "description": "New desc",    # optional
            "is_primary": true            # optional
        }

    Returns:
        {
            "success": true,
            "asset": { ... updated ... },
            "message": "Brand asset updated successfully"
        }
    """
    try:
        user_id = g.user_id
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "No update data provided"
            }), 400

        updated_asset = brand_asset_service.update_asset(
            user_id=user_id,
            asset_id=asset_id,
            name=data.get('name'),
            description=data.get('description'),
            metadata=data.get('metadata'),
            is_primary=data.get('is_primary')
        )

        if not updated_asset:
            return jsonify({
                "success": False,
                "error": "Brand asset not found"
            }), 404

        return jsonify({
            "success": True,
            "asset": updated_asset,
            "message": "Brand asset updated successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to update brand asset: {str(e)}"
        }), 500


@brand_bp.route('/brand/assets/<asset_id>', methods=['DELETE'])
def delete_asset(asset_id: str):
    """
    Delete a brand asset and its file.

    Returns:
        {
            "success": true,
            "message": "Brand asset deleted successfully"
        }
    """
    try:
        user_id = g.user_id
        success = brand_asset_service.delete_asset(user_id, asset_id)

        if not success:
            return jsonify({
                "success": False,
                "error": "Brand asset not found"
            }), 404

        return jsonify({
            "success": True,
            "message": "Brand asset deleted successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to delete brand asset: {str(e)}"
        }), 500


@brand_bp.route('/brand/assets/<asset_id>/download', methods=['GET'])
def download_asset(asset_id: str):
    """
    Download a brand asset file, proxied through the backend.

    Educational Note: In Docker, Supabase storage signed URLs use internal
    hostnames (e.g. supabase-kong:8000) that browsers can't resolve.
    Instead of returning a signed URL, we download the file server-side
    and stream it to the browser — same pattern used by studio endpoints.
    """
    try:
        user_id = g.user_id
        asset = brand_asset_service.get_asset(user_id, asset_id)

        if not asset:
            return jsonify({
                "success": False,
                "error": "Brand asset not found"
            }), 404

        data = storage_service.download_brand_asset(
            user_id=user_id,
            asset_id=asset_id,
            filename=asset["file_name"]
        )

        if not data:
            return jsonify({
                "success": False,
                "error": "Asset file not found in storage"
            }), 404

        mimetype = asset.get("mime_type", "application/octet-stream")
        return send_file(io.BytesIO(data), mimetype=mimetype, as_attachment=False)

    except Exception as e:
        logger.exception("Failed to download brand asset %s", asset_id)
        return jsonify({
            "success": False,
            "error": "Failed to download brand asset"
        }), 500


@brand_bp.route('/brand/assets/<asset_id>/primary', methods=['POST'])
def set_asset_primary(asset_id: str):
    """
    Set a brand asset as the primary for its type.

    Returns:
        {
            "success": true,
            "message": "Asset set as primary"
        }
    """
    try:
        user_id = g.user_id

        # Get asset to find its type
        asset = brand_asset_service.get_asset(user_id, asset_id)
        if not asset:
            return jsonify({
                "success": False,
                "error": "Brand asset not found"
            }), 404

        success = brand_asset_service.set_primary(
            user_id, asset_id, asset['asset_type']
        )

        if not success:
            return jsonify({
                "success": False,
                "error": "Failed to set asset as primary"
            }), 500

        return jsonify({
            "success": True,
            "message": f"Asset set as primary {asset['asset_type']}"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# BRAND CONFIG ENDPOINTS
# =============================================================================

@brand_bp.route('/brand/config', methods=['GET'])
def get_config():
    """
    Get the brand configuration for the authenticated user.

    Educational Note: Creates default config if none exists. This ensures
    there's always a valid config to display.

    Returns:
        {
            "success": true,
            "config": {
                "colors": {...},
                "typography": {...},
                "guidelines": "...",
                "best_practices": {...},
                "voice": {...},
                "feature_settings": {...}
            }
        }
    """
    try:
        user_id = g.user_id
        config = brand_config_service.get_config(user_id)

        return jsonify({
            "success": True,
            "config": config
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@brand_bp.route('/brand/config', methods=['PUT'])
def update_config():
    """
    Update the brand configuration (full or partial).

    Request Body (all fields optional):
        {
            "colors": {...},
            "typography": {...},
            "spacing": {...},
            "guidelines": "...",
            "best_practices": {...},
            "voice": {...},
            "feature_settings": {...}
        }

    Returns:
        {
            "success": true,
            "config": { ... updated ... },
            "message": "Brand config updated successfully"
        }
    """
    try:
        user_id = g.user_id
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "No update data provided"
            }), 400

        updated_config = brand_config_service.update_config(
            user_id=user_id,
            colors=data.get('colors'),
            typography=data.get('typography'),
            spacing=data.get('spacing'),
            guidelines=data.get('guidelines'),
            best_practices=data.get('best_practices'),
            voice=data.get('voice'),
            feature_settings=data.get('feature_settings')
        )

        return jsonify({
            "success": True,
            "config": updated_config,
            "message": "Brand config updated successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to update brand config: {str(e)}"
        }), 500


@brand_bp.route('/brand/config/colors', methods=['PUT'])
def update_colors():
    """
    Update just the color palette.

    Request Body:
        {
            "colors": {
                "primary": "#000000",
                "secondary": "#666666",
                "accent": "#0066CC",
                "background": "#FFFFFF",
                "text": "#1A1A1A",
                "custom": [
                    { "name": "Brand Red", "value": "#FF0000" }
                ]
            }
        }
    """
    try:
        user_id = g.user_id
        data = request.get_json()

        if not data or 'colors' not in data:
            return jsonify({
                "success": False,
                "error": "Colors data is required"
            }), 400

        updated_config = brand_config_service.update_colors(
            user_id, data['colors']
        )

        return jsonify({
            "success": True,
            "config": updated_config,
            "message": "Brand colors updated successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to update brand colors: {str(e)}"
        }), 500


@brand_bp.route('/brand/config/typography', methods=['PUT'])
def update_typography():
    """
    Update just the typography settings.

    Request Body:
        {
            "typography": {
                "heading_font": "Inter",
                "body_font": "Inter",
                "heading_sizes": {"h1": "2.5rem", "h2": "2rem", "h3": "1.5rem"},
                "body_size": "1rem",
                "line_height": "1.6"
            }
        }
    """
    try:
        user_id = g.user_id
        data = request.get_json()

        if not data or 'typography' not in data:
            return jsonify({
                "success": False,
                "error": "Typography data is required"
            }), 400

        updated_config = brand_config_service.update_typography(
            user_id, data['typography']
        )

        return jsonify({
            "success": True,
            "config": updated_config,
            "message": "Brand typography updated successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to update brand typography: {str(e)}"
        }), 500


@brand_bp.route('/brand/config/guidelines', methods=['PUT'])
def update_guidelines():
    """
    Update just the brand guidelines text.

    Request Body:
        {
            "guidelines": "# Brand Guidelines\n\nOur brand is..."
        }
    """
    try:
        user_id = g.user_id
        data = request.get_json()

        if not data or 'guidelines' not in data:
            return jsonify({
                "success": False,
                "error": "Guidelines text is required"
            }), 400

        updated_config = brand_config_service.update_guidelines(
            user_id, data['guidelines']
        )

        return jsonify({
            "success": True,
            "config": updated_config,
            "message": "Brand guidelines updated successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to update brand guidelines: {str(e)}"
        }), 500


@brand_bp.route('/brand/config/voice', methods=['PUT'])
def update_voice():
    """
    Update just the brand voice settings.

    Request Body:
        {
            "voice": {
                "tone": "professional",
                "personality": ["friendly", "knowledgeable"],
                "keywords": ["innovation", "quality"]
            }
        }
    """
    try:
        user_id = g.user_id
        data = request.get_json()

        if not data or 'voice' not in data:
            return jsonify({
                "success": False,
                "error": "Voice data is required"
            }), 400

        updated_config = brand_config_service.update_voice(
            user_id, data['voice']
        )

        return jsonify({
            "success": True,
            "config": updated_config,
            "message": "Brand voice updated successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to update brand voice: {str(e)}"
        }), 500


@brand_bp.route('/brand/config/features', methods=['PUT'])
def update_feature_settings():
    """
    Update per-feature brand application settings.

    Educational Note: This controls which studio features should apply
    the brand configuration. For example, mind maps might not need
    brand colors but presentations do.

    Request Body:
        {
            "feature_settings": {
                "infographic": true,
                "presentation": true,
                "mind_map": false,
                "blog": true,
                "email": true
            }
        }
    """
    try:
        user_id = g.user_id
        data = request.get_json()

        if not data or 'feature_settings' not in data:
            return jsonify({
                "success": False,
                "error": "Feature settings data is required"
            }), 400

        updated_config = brand_config_service.update_feature_settings(
            user_id, data['feature_settings']
        )

        return jsonify({
            "success": True,
            "config": updated_config,
            "message": "Feature settings updated successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to update feature settings: {str(e)}"
        }), 500
