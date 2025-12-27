"""
File Utilities - Validation and metadata for file uploads.

Educational Note: These utilities handle file type validation and metadata
extraction. They are stateless functions that can be used across services.
"""

from pathlib import Path
from typing import Dict, Tuple, Optional


# Size limits (in bytes)
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB per image


# Allowed file extensions and their categories
ALLOWED_EXTENSIONS: Dict[str, str] = {
    # Documents
    '.pdf': 'document',
    '.txt': 'document',
    '.docx': 'document',
    '.pptx': 'document',
    # Audio (transcribed via ElevenLabs)
    '.mp3': 'audio',
    '.wav': 'audio',
    '.m4a': 'audio',
    '.aac': 'audio',
    '.flac': 'audio',
    # Images (max 5MB per image)
    '.jpeg': 'image',
    '.jpg': 'image',
    '.png': 'image',
    '.gif': 'image',
    '.webp': 'image',
    # Data
    '.csv': 'data',
    # Links (stored as JSON with URL metadata)
    '.link': 'link',
}

# MIME type mappings
MIME_TYPES: Dict[str, str] = {
    '.pdf': 'application/pdf',
    '.txt': 'text/plain',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.m4a': 'audio/mp4',
    '.aac': 'audio/aac',
    '.flac': 'audio/flac',
    '.jpeg': 'image/jpeg',
    '.jpg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.csv': 'text/csv',
    '.link': 'application/json',
}


def is_allowed_file(filename: str) -> bool:
    """
    Check if a file extension is allowed.

    Educational Note: We validate file extensions for security
    and to ensure we can process the file type.

    Args:
        filename: The filename to check

    Returns:
        True if the extension is allowed, False otherwise
    """
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def get_file_info(filename: str) -> Tuple[str, str, str]:
    """
    Get file extension, category, and MIME type.

    Args:
        filename: The filename to analyze

    Returns:
        Tuple of (extension, category, mime_type)
    """
    ext = Path(filename).suffix.lower()
    category = ALLOWED_EXTENSIONS.get(ext, 'unknown')
    mime_type = MIME_TYPES.get(ext, 'application/octet-stream')
    return ext, category, mime_type


def get_allowed_extensions() -> Dict[str, str]:
    """
    Get the allowed file extensions and their categories.

    Returns:
        Dictionary mapping extensions to categories
    """
    return ALLOWED_EXTENSIONS.copy()


def get_extensions_by_category() -> Dict[str, list]:
    """
    Get allowed extensions grouped by category.

    Returns:
        Dictionary mapping categories to lists of extensions
    """
    by_category: Dict[str, list] = {}
    for ext, category in ALLOWED_EXTENSIONS.items():
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(ext)
    return by_category


def validate_file_size(filename: str, file_size: int) -> Optional[str]:
    """
    Validate file size based on file type.

    Educational Note: Different file types have different size limits.
    Images are limited to 5MB per file (API constraint).

    Args:
        filename: The filename to check
        file_size: Size of the file in bytes

    Returns:
        Error message if validation fails, None if valid
    """
    ext = Path(filename).suffix.lower()
    category = ALLOWED_EXTENSIONS.get(ext)

    if category == 'image' and file_size > MAX_IMAGE_SIZE:
        max_mb = MAX_IMAGE_SIZE / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        return f"Image file too large. Maximum {max_mb:.0f}MB allowed, got {actual_mb:.1f}MB"

    return None
