"""
Logo resolution utilities for studio routes.

Shared helpers for resolving brand logo/icon bytes from brand assets
or project image sources. Used by social posts and ad creatives routes
to pass logo images to Gemini's multimodal image generation.

SVG logos are automatically converted to PNG since Gemini cannot process SVG input.
"""
import logging
from typing import Optional, Tuple

from flask import g

from app.services.integrations.supabase import storage_service

logger = logging.getLogger(__name__)


def _convert_svg_to_png(svg_bytes: bytes) -> Optional[bytes]:
    """
    Convert SVG bytes to PNG using cairosvg.

    Returns PNG bytes on success, None if cairosvg is unavailable or conversion fails.
    """
    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=svg_bytes)
    except ImportError:
        logger.warning("cairosvg not installed — cannot convert SVG logo to PNG. pip install cairosvg")
        return None
    except Exception as e:
        logger.warning("SVG to PNG conversion failed: %s", e)
        return None


def _ensure_png(image_bytes: bytes, mime_type: str) -> Tuple[Optional[bytes], str]:
    """
    If the image is SVG, convert to PNG. Otherwise return as-is.

    Returns:
        Tuple of (image_bytes, mime_type). Bytes is None if SVG conversion failed.
    """
    if mime_type == "image/svg+xml":
        png_bytes = _convert_svg_to_png(image_bytes)
        if png_bytes:
            return png_bytes, "image/png"
        return None, "image/png"
    return image_bytes, mime_type


def resolve_brand_logo() -> Tuple[Optional[bytes], str]:
    """
    Fetch brand icon (or logo fallback) for the current user.

    Checks for a primary icon first, then falls back to primary logo.
    Requires Flask request context (uses g.user_id).
    SVG logos are automatically converted to PNG.

    Returns:
        Tuple of (image_bytes, mime_type). Bytes is None if not found.
    """
    from app.services.data_services.brand_asset_service import brand_asset_service

    try:
        user_id = g.user_id
        # Prefer primary icon, fall back to primary logo
        icon = brand_asset_service.get_primary_asset(user_id, 'icon')
        if not icon:
            icon = brand_asset_service.get_primary_asset(user_id, 'logo')

        if icon:
            image_bytes = storage_service.download_brand_asset(
                user_id, icon['id'], icon['file_name']
            )
            mime_type = icon.get('mime_type', 'image/png')
            if image_bytes:
                # Convert SVG to PNG since Gemini can't process SVG
                image_bytes, mime_type = _ensure_png(image_bytes, mime_type)
                if image_bytes:
                    logger.info("Resolved brand logo (type=%s)", icon.get('asset_type'))
                    return image_bytes, mime_type
    except Exception as e:
        logger.warning("Failed to fetch brand icon: %s", e)

    return None, "image/png"


def resolve_source_logo(project_id: str, source_id: str) -> Tuple[Optional[bytes], str]:
    """
    Fetch an image source's raw file to use as a logo.

    Only works for IMAGE type sources. Downloads the raw file from
    Supabase Storage. SVG images are automatically converted to PNG.

    Args:
        project_id: The project UUID
        source_id: The source UUID (must be IMAGE type)

    Returns:
        Tuple of (image_bytes, mime_type). Bytes is None if not found.
    """
    from app.services.source_services.source_service import source_service

    try:
        source = source_service.get_source(project_id, source_id)
        if source and source.get('type') == 'IMAGE':
            embedding_info = source.get('embedding_info', {})
            stored_filename = embedding_info.get('stored_filename', '')
            if stored_filename:
                image_bytes = storage_service.download_raw_file(
                    project_id, source_id, stored_filename
                )
                mime_type = embedding_info.get('mime_type', 'image/png')
                if image_bytes:
                    # Convert SVG to PNG since Gemini can't process SVG
                    image_bytes, mime_type = _ensure_png(image_bytes, mime_type)
                    if image_bytes:
                        logger.info("Resolved source image as logo (source=%s)", source_id)
                        return image_bytes, mime_type
    except Exception as e:
        logger.warning("Failed to fetch source image as logo: %s", e)

    return None, "image/png"


def _first_image_source_id(project_id: str, source_ids: list) -> Optional[str]:
    """
    Scan a list of source ids and return the first one of type IMAGE.

    Used to auto-detect a user-uploaded logo when no brand icon is set.
    """
    from app.services.source_services.source_service import source_service

    for sid in source_ids or []:
        try:
            src = source_service.get_source(project_id, sid)
            if src and src.get('type') == 'IMAGE':
                return sid
        except Exception as e:
            logger.warning("Failed to inspect source %s while auto-detecting logo: %s", sid, e)
    return None


def resolve_logo(data: dict, project_id: str) -> Tuple[Optional[bytes], str]:
    """
    Resolve logo bytes from request data.

    Reads logo_source and logo_source_id from the request body and
    resolves the logo image accordingly.

    Resolution order for 'auto':
      1. Brand icon / logo (from brand assets)
      2. First IMAGE-type source in `data['source_ids']` (chat-supplied context)

    Args:
        data: Request JSON body
        project_id: The project UUID

    Returns:
        Tuple of (image_bytes, mime_type). Bytes is None if no logo found.
    """
    logo_source = data.get('logo_source', 'auto')

    if logo_source == 'source' and data.get('logo_source_id'):
        return resolve_source_logo(project_id, data['logo_source_id'])

    if logo_source in ('brand_icon', 'auto'):
        image_bytes, mime_type = resolve_brand_logo()
        if image_bytes:
            return image_bytes, mime_type

        # Fallback: when 'auto' and no brand asset, look for an image source
        # the user attached to the project (e.g. uploaded their logo as a source).
        if logo_source == 'auto':
            fallback_id = _first_image_source_id(project_id, data.get('source_ids') or [])
            if fallback_id:
                return resolve_source_logo(project_id, fallback_id)

    return None, "image/png"
