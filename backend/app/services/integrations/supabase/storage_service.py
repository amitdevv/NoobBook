"""
Supabase Storage Service - File upload/download operations.

Educational Note: Supabase Storage provides S3-compatible file storage.
Files are organized in buckets:
- raw-files: Original uploaded files (PDFs, images, audio)
- processed-files: Extracted text content
- chunks: Text chunks for RAG search
- studio-outputs: Generated content (audio, video, documents)

File paths follow the pattern: {project_id}/{source_id}/{filename}
"""
import logging
from typing import Optional, BinaryIO, List, Dict, Any
from pathlib import Path

from app.services.integrations.supabase import get_supabase, is_supabase_enabled

logger = logging.getLogger(__name__)


# Bucket names
BUCKET_RAW = "raw-files"
BUCKET_PROCESSED = "processed-files"
BUCKET_CHUNKS = "chunks"
BUCKET_STUDIO = "studio-outputs"
BUCKET_BRAND_ASSETS = "brand-assets"

# Supabase storage3 defaults to limit=100 which silently drops entries.
# Use a high limit to ensure we list all files in a folder.
_LIST_OPTIONS = {"limit": 10000}


def _get_client():
    """Get Supabase client, raising error if not configured."""
    if not is_supabase_enabled():
        raise RuntimeError(
            "Supabase is not configured. Please add SUPABASE_URL and "
            "SUPABASE_ANON_KEY to your .env file."
        )
    return get_supabase()


def _build_path(project_id: str, source_id: str, filename: str) -> str:
    """Build storage path: project_id/source_id/filename"""
    return f"{project_id}/{source_id}/{filename}"


# =============================================================================
# RAW FILES (Original uploads)
# =============================================================================

def upload_raw_file(
    project_id: str,
    source_id: str,
    filename: str,
    file_data: bytes,
    content_type: str = "application/octet-stream"
) -> Optional[str]:
    """
    Upload a raw file to storage.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        filename: Original filename
        file_data: File bytes
        content_type: MIME type

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    path = _build_path(project_id, source_id, filename)

    try:
        client.storage.from_(BUCKET_RAW).upload(
            path=path,
            file=file_data,
            file_options={"content-type": content_type}
        )
        return path
    except Exception as e:
        logger.error("Failed to upload raw file %s: %s", path, e)
        return None


def download_raw_file(project_id: str, source_id: str, filename: str) -> Optional[bytes]:
    """
    Download a raw file from storage.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        filename: Original filename

    Returns:
        File bytes or None if not found
    """
    client = _get_client()
    path = _build_path(project_id, source_id, filename)

    try:
        response = client.storage.from_(BUCKET_RAW).download(path)
        return response
    except Exception as e:
        logger.error("Failed to download raw file %s: %s", path, e)
        return None


def delete_raw_file(project_id: str, source_id: str, filename: str) -> bool:
    """Delete a raw file from storage."""
    client = _get_client()
    path = _build_path(project_id, source_id, filename)

    try:
        client.storage.from_(BUCKET_RAW).remove([path])
        return True
    except Exception as e:
        logger.error("Failed to delete raw file %s: %s", path, e)
        return False


def get_raw_file_url(project_id: str, source_id: str, filename: str, expires_in: int = 3600) -> Optional[str]:
    """
    Get a signed URL for a raw file.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        filename: Original filename
        expires_in: URL expiration time in seconds (default 1 hour)

    Returns:
        Signed URL or None
    """
    client = _get_client()
    path = _build_path(project_id, source_id, filename)

    try:
        response = client.storage.from_(BUCKET_RAW).create_signed_url(path, expires_in)
        return response.get("signedURL")
    except Exception as e:
        logger.error("Failed to get signed URL for %s: %s", path, e)
        return None


# =============================================================================
# PROCESSED FILES (Extracted text)
# =============================================================================

def upload_processed_file(
    project_id: str,
    source_id: str,
    content: str
) -> Optional[str]:
    """
    Upload processed text content to storage.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        content: Extracted text content

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    filename = f"{source_id}.txt"
    path = _build_path(project_id, source_id, filename)

    try:
        client.storage.from_(BUCKET_PROCESSED).upload(
            path=path,
            file=content.encode("utf-8"),
            file_options={"content-type": "text/plain; charset=utf-8"}
        )
        return path
    except Exception as e:
        logger.error("Failed to upload processed file %s: %s", path, e)
        return None


def download_processed_file(project_id: str, source_id: str) -> Optional[str]:
    """
    Download processed text content from storage.

    Args:
        project_id: The project UUID
        source_id: The source UUID

    Returns:
        Text content or None if not found
    """
    client = _get_client()
    filename = f"{source_id}.txt"
    path = _build_path(project_id, source_id, filename)

    try:
        response = client.storage.from_(BUCKET_PROCESSED).download(path)
        return response.decode("utf-8")
    except Exception as e:
        logger.error("Failed to download processed file %s: %s", path, e)
        return None


def delete_processed_file(project_id: str, source_id: str) -> bool:
    """Delete a processed file from storage."""
    client = _get_client()
    filename = f"{source_id}.txt"
    path = _build_path(project_id, source_id, filename)

    try:
        client.storage.from_(BUCKET_PROCESSED).remove([path])
        return True
    except Exception as e:
        logger.error("Failed to delete processed file %s: %s", path, e)
        return False


# =============================================================================
# CHUNKS (Text chunks for RAG)
# =============================================================================

def upload_chunk(
    project_id: str,
    source_id: str,
    chunk_id: str,
    content: str
) -> Optional[str]:
    """
    Upload a text chunk to storage.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        chunk_id: The chunk ID (e.g., source_id_page_1_chunk_1)
        content: Chunk text content

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    filename = f"{chunk_id}.txt"
    path = _build_path(project_id, source_id, filename)

    try:
        client.storage.from_(BUCKET_CHUNKS).upload(
            path=path,
            file=content.encode("utf-8"),
            file_options={"content-type": "text/plain; charset=utf-8"}
        )
        return path
    except Exception as e:
        logger.error("Failed to upload chunk %s: %s", path, e)
        return None


def download_chunk(project_id: str, source_id: str, chunk_id: str) -> Optional[str]:
    """
    Download a text chunk from storage.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        chunk_id: The chunk ID

    Returns:
        Chunk text content or None if not found
    """
    client = _get_client()
    filename = f"{chunk_id}.txt"
    path = _build_path(project_id, source_id, filename)

    try:
        response = client.storage.from_(BUCKET_CHUNKS).download(path)
        return response.decode("utf-8")
    except Exception as e:
        logger.error("Failed to download chunk %s: %s", path, e)
        return None


def list_source_chunks(project_id: str, source_id: str) -> List[Dict[str, Any]]:
    """
    List and download all chunks for a source.

    Educational Note: This function retrieves all chunks from Supabase Storage
    for use in RAG search. Returns chunk data as a list of dicts with
    chunk_id, text, page_number, and source_id.

    Args:
        project_id: The project UUID
        source_id: The source UUID

    Returns:
        List of chunk dicts with chunk_id, text, page_number, source_id
    """
    client = _get_client()
    prefix = f"{project_id}/{source_id}"

    try:
        # List all files in the source's chunk folder
        files = client.storage.from_(BUCKET_CHUNKS).list(
            prefix, options=_LIST_OPTIONS
        )
        if not files:
            return []

        # Filter to .txt files only
        txt_files = [f for f in files if f.get("name", "").endswith(".txt")]
        if not txt_files:
            return []

        def _download_chunk(file_info):
            """Download a single chunk file and parse its metadata."""
            filename = file_info["name"]
            chunk_id = filename[:-4]  # Remove .txt
            path = f"{prefix}/{filename}"
            try:
                response = client.storage.from_(BUCKET_CHUNKS).download(path)
                text = response.decode("utf-8")

                # Parse page number from chunk_id
                # Format: {source_id}_page_{page}_chunk_{n}
                page_number = 1
                if "_page_" in chunk_id:
                    try:
                        page_part = chunk_id.split("_page_")[1]
                        page_number = int(page_part.split("_chunk_")[0])
                    except (IndexError, ValueError):
                        pass

                return {
                    "chunk_id": chunk_id,
                    "text": text,
                    "page_number": page_number,
                    "source_id": source_id
                }
            except Exception as e:
                logger.error("Failed to download chunk %s: %s", chunk_id, e)
                return None

        # Download chunks concurrently to avoid N+1 sequential requests
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(_download_chunk, txt_files))

        chunks = [r for r in results if r is not None]

        # Sort by chunk_id for consistent ordering
        chunks.sort(key=lambda c: c.get("chunk_id", ""))
        return chunks

    except Exception as e:
        logger.error("Failed to list chunks for %s: %s", prefix, e)
        return []


def delete_source_chunks(project_id: str, source_id: str) -> bool:
    """
    Delete all chunks for a source.

    Args:
        project_id: The project UUID
        source_id: The source UUID

    Returns:
        True if successful
    """
    client = _get_client()
    prefix = f"{project_id}/{source_id}/"

    try:
        # List all files with prefix
        files = client.storage.from_(BUCKET_CHUNKS).list(
            prefix, options=_LIST_OPTIONS
        )
        if files:
            paths = [f"{prefix}{f['name']}" for f in files]
            client.storage.from_(BUCKET_CHUNKS).remove(paths)
        return True
    except Exception as e:
        logger.error("Failed to delete chunks for %s: %s", prefix, e)
        return False


# =============================================================================
# STUDIO OUTPUTS (Generated content - PRDs, blogs, emails, etc.)
# =============================================================================

def _build_studio_path(project_id: str, job_type: str, job_id: str, filename: str) -> str:
    """
    Build storage path for studio outputs.
    Pattern: {project_id}/{job_type}/{job_id}/{filename}
    Example: abc123/prds/def456/def456.md
    """
    return f"{project_id}/{job_type}/{job_id}/{filename}"


def upload_studio_file(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str,
    content: str,
    content_type: str = "text/plain; charset=utf-8"
) -> Optional[str]:
    """
    Upload a studio output file to storage.

    Args:
        project_id: The project UUID
        job_type: Type of studio output (prds, blogs, emails, etc.)
        job_id: The job UUID
        filename: Output filename (e.g., job_id.md)
        content: File content as string
        content_type: MIME type

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        # Try to upload (will fail if file exists)
        client.storage.from_(BUCKET_STUDIO).upload(
            path=path,
            file=content.encode("utf-8"),
            file_options={"content-type": content_type}
        )
        return path
    except Exception as e:
        # If file exists, try to update it
        if "Duplicate" in str(e) or "already exists" in str(e).lower():
            try:
                client.storage.from_(BUCKET_STUDIO).update(
                    path=path,
                    file=content.encode("utf-8"),
                    file_options={"content-type": content_type}
                )
                return path
            except Exception as update_e:
                logger.error("Failed to update studio file %s: %s", path, update_e)
                return None
        logger.error("Failed to upload studio file %s: %s", path, e)
        return None


def append_studio_file(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str,
    content: str
) -> Optional[str]:
    """
    Append content to an existing studio file.

    Educational Note: Supabase Storage doesn't support append, so we
    download existing content, append new content, then re-upload.

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID
        filename: Output filename
        content: Content to append

    Returns:
        Storage path if successful, None otherwise
    """
    # Download existing content
    existing = download_studio_file(project_id, job_type, job_id, filename)

    if existing is None:
        # File doesn't exist, create new
        return upload_studio_file(project_id, job_type, job_id, filename, content)

    # Append and re-upload
    new_content = existing + content
    return upload_studio_file(project_id, job_type, job_id, filename, new_content)


def download_studio_file(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str
) -> Optional[str]:
    """
    Download a studio output file from storage.

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID
        filename: Output filename

    Returns:
        File content as string or None if not found
    """
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        response = client.storage.from_(BUCKET_STUDIO).download(path)
        return response.decode("utf-8")
    except Exception as e:
        logger.error("Failed to download studio file %s: %s", path, e)
        return None


def delete_studio_file(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str
) -> bool:
    """Delete a studio output file from storage."""
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        client.storage.from_(BUCKET_STUDIO).remove([path])
        return True
    except Exception as e:
        logger.error("Failed to delete studio file %s: %s", path, e)
        return False


def delete_studio_job_files(project_id: str, job_type: str, job_id: str) -> bool:
    """
    Delete all files for a studio job, including subdirectories.

    Educational Note: Supabase .list() only returns immediate children.
    For jobs with subdirectories (e.g., websites with assets/, presentations
    with slides/ and screenshots/), we iterate through folders to find all files.

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID

    Returns:
        True if successful
    """
    client = _get_client()
    root_prefix = f"{project_id}/{job_type}/{job_id}"

    try:
        # Iteratively scan folders to collect all file paths
        folders_to_scan = [root_prefix]
        all_paths = []

        while folders_to_scan:
            folder = folders_to_scan.pop()
            entries = client.storage.from_(BUCKET_STUDIO).list(
                folder, options=_LIST_OPTIONS
            )
            if not entries:
                continue
            for entry in entries:
                path = f"{folder}/{entry['name']}"
                if entry.get("id") is None:
                    # No id means it's a folder — recurse into it
                    folders_to_scan.append(path)
                else:
                    all_paths.append(path)

        if all_paths:
            client.storage.from_(BUCKET_STUDIO).remove(all_paths)
        return True
    except Exception as e:
        logger.error("Failed to delete studio job files for %s: %s", job_id, e)
        return False


def list_studio_job_files(project_id: str, job_type: str, job_id: str) -> List[Dict[str, Any]]:
    """
    List all files for a studio job, including subdirectories.

    Educational Note: Used for ZIP downloads (websites, presentations) where
    we need to enumerate all files in the job folder. Iterates through
    subdirectories since Supabase .list() only returns immediate children.

    Args:
        project_id: The project UUID
        job_type: Type of studio output (websites, presentations, etc.)
        job_id: The job UUID

    Returns:
        List of file info dicts with 'name' as relative path from job root,
        or empty list on error
    """
    client = _get_client()
    root_prefix = f"{project_id}/{job_type}/{job_id}"

    try:
        # Iteratively scan folders to collect all files
        folders_to_scan = [root_prefix]
        all_files = []

        while folders_to_scan:
            folder = folders_to_scan.pop()
            entries = client.storage.from_(BUCKET_STUDIO).list(
                folder, options=_LIST_OPTIONS
            )
            if not entries:
                continue
            for entry in entries:
                path = f"{folder}/{entry['name']}"
                if entry.get("id") is None:
                    # No id means it's a folder — recurse into it
                    folders_to_scan.append(path)
                else:
                    # Store with relative path from job root for ZIP structure
                    relative_path = path[len(root_prefix) + 1:]  # Strip prefix + /
                    file_info = {**entry, "name": relative_path}
                    all_files.append(file_info)

        return all_files
    except Exception as e:
        logger.error("Failed to list studio job files for %s: %s", root_prefix, e)
        return []


def upload_studio_binary(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str,
    file_data: bytes,
    content_type: str = "application/octet-stream"
) -> Optional[str]:
    """
    Upload a binary file (image, video, etc.) to studio outputs in Supabase.

    Args:
        project_id: The project UUID
        job_type: Type of studio output (blogs, etc.)
        job_id: The job UUID
        filename: Output filename (e.g., image.png)
        file_data: Binary file data
        content_type: MIME type (e.g., image/png)

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        client.storage.from_(BUCKET_STUDIO).upload(
            path=path,
            file=file_data,
            file_options={"content-type": content_type}
        )
        return path
    except Exception as e:
        if "Duplicate" in str(e) or "already exists" in str(e).lower():
            try:
                client.storage.from_(BUCKET_STUDIO).update(
                    path=path,
                    file=file_data,
                    file_options={"content-type": content_type}
                )
                return path
            except Exception as update_e:
                logger.error("Failed to update studio binary %s: %s", path, update_e)
                return None
        logger.error("Failed to upload studio binary %s: %s", path, e)
        return None


def download_studio_binary(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str
) -> Optional[bytes]:
    """
    Download a binary file from Supabase studio outputs.

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID
        filename: Output filename

    Returns:
        File bytes or None if not found
    """
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        response = client.storage.from_(BUCKET_STUDIO).download(path)
        return response
    except Exception as e:
        logger.error("Failed to download studio binary %s: %s", path, e)
        return None


def get_studio_public_url(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str
) -> str:
    """
    Get the public URL for a studio file.

    Educational Note: This returns a direct public URL if bucket is public,
    otherwise use get_studio_signed_url for private buckets.

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID
        filename: Output filename

    Returns:
        Public URL string
    """
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        response = client.storage.from_(BUCKET_STUDIO).get_public_url(path)
        return response
    except Exception as e:
        logger.error("Failed to get public URL for %s: %s", path, e)
        return ""


def get_studio_signed_url(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str,
    expires_in: int = 3600
) -> Optional[str]:
    """
    Get a signed URL for a studio file (for private buckets).

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID
        filename: Output filename
        expires_in: URL expiration time in seconds (default 1 hour)

    Returns:
        Signed URL or None
    """
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        response = client.storage.from_(BUCKET_STUDIO).create_signed_url(path, expires_in)
        return response.get("signedURL")
    except Exception as e:
        logger.error("Failed to get signed URL for %s: %s", path, e)
        return None


# =============================================================================
# AI IMAGES (Generated charts/plots from analysis)
# =============================================================================

def upload_ai_image(
    project_id: str,
    filename: str,
    file_data: bytes,
    content_type: str = "image/png"
) -> Optional[str]:
    """
    Upload an AI-generated image to the studio-outputs bucket.

    Educational Note: AI-generated images (e.g., matplotlib charts from
    CSV analysis) are stored in Supabase Storage instead of local disk.
    Path pattern: {project_id}/ai-images/{filename}

    Args:
        project_id: The project UUID
        filename: Image filename (e.g., source_id_plot_uuid.png)
        file_data: Image bytes
        content_type: MIME type (default image/png)

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    path = f"{project_id}/ai-images/{filename}"

    try:
        client.storage.from_(BUCKET_STUDIO).upload(
            path=path,
            file=file_data,
            file_options={"content-type": content_type}
        )
        return path
    except Exception as e:
        if "Duplicate" in str(e) or "already exists" in str(e).lower():
            try:
                client.storage.from_(BUCKET_STUDIO).update(
                    path=path,
                    file=file_data,
                    file_options={"content-type": content_type}
                )
                return path
            except Exception as update_e:
                logger.error("Failed to update AI image %s: %s", path, update_e)
                return None
        logger.error("Failed to upload AI image %s: %s", path, e)
        return None


def download_ai_image(project_id: str, filename: str) -> Optional[bytes]:
    """
    Download an AI-generated image from the studio-outputs bucket.

    Args:
        project_id: The project UUID
        filename: Image filename

    Returns:
        Image bytes or None if not found
    """
    client = _get_client()
    path = f"{project_id}/ai-images/{filename}"

    try:
        response = client.storage.from_(BUCKET_STUDIO).download(path)
        return response
    except Exception as e:
        logger.error("Failed to download AI image %s: %s", path, e)
        return None


def get_ai_image_url(
    project_id: str,
    filename: str,
    expires_in: int = 3600
) -> Optional[str]:
    """
    Get a signed URL for an AI-generated image.

    Args:
        project_id: The project UUID
        filename: Image filename
        expires_in: URL expiration in seconds (default 1 hour)

    Returns:
        Signed URL or None
    """
    client = _get_client()
    path = f"{project_id}/ai-images/{filename}"

    try:
        response = client.storage.from_(BUCKET_STUDIO).create_signed_url(path, expires_in)
        return response.get("signedURL")
    except Exception as e:
        logger.error("Failed to get AI image URL for %s: %s", path, e)
        return None


# =============================================================================
# CLEANUP - Delete all files for a source
# =============================================================================

def delete_source_files(project_id: str, source_id: str, filename: str) -> bool:
    """
    Delete all files associated with a source.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        filename: Original filename for raw file

    Returns:
        True if all deletions successful
    """
    results = []

    # Delete raw file
    results.append(delete_raw_file(project_id, source_id, filename))

    # Delete processed file
    results.append(delete_processed_file(project_id, source_id))

    # Delete chunks
    results.append(delete_source_chunks(project_id, source_id))

    return all(results)


# =============================================================================
# BRAND ASSETS (Logos, icons, fonts, images for brand kit)
# =============================================================================

def _build_brand_path(user_id: str, asset_id: str, filename: str) -> str:
    """
    Build storage path for brand assets.
    Pattern: {user_id}/brand/{asset_id}/{filename}
    Example: abc123/brand/def456/logo.svg
    """
    return f"{user_id}/brand/{asset_id}/{filename}"


def upload_brand_asset(
    user_id: str,
    asset_id: str,
    filename: str,
    file_data: bytes,
    content_type: str = "application/octet-stream"
) -> Optional[str]:
    """
    Upload a brand asset file to storage.

    Args:
        user_id: The user UUID
        asset_id: The brand asset UUID
        filename: Asset filename (e.g., logo.svg)
        file_data: File bytes
        content_type: MIME type

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    path = _build_brand_path(user_id, asset_id, filename)

    try:
        client.storage.from_(BUCKET_BRAND_ASSETS).upload(
            path=path,
            file=file_data,
            file_options={"content-type": content_type}
        )
        return path
    except Exception as e:
        # If file exists, try to update it
        if "Duplicate" in str(e) or "already exists" in str(e).lower():
            try:
                client.storage.from_(BUCKET_BRAND_ASSETS).update(
                    path=path,
                    file=file_data,
                    file_options={"content-type": content_type}
                )
                return path
            except Exception as update_e:
                logger.error("Failed to update brand asset %s: %s", path, update_e)
                return None
        logger.error("Failed to upload brand asset %s: %s", path, e)
        return None


def download_brand_asset(
    user_id: str,
    asset_id: str,
    filename: str
) -> Optional[bytes]:
    """
    Download a brand asset file from storage.

    Args:
        user_id: The user UUID
        asset_id: The brand asset UUID
        filename: Asset filename

    Returns:
        File bytes or None if not found
    """
    client = _get_client()
    path = _build_brand_path(user_id, asset_id, filename)

    try:
        response = client.storage.from_(BUCKET_BRAND_ASSETS).download(path)
        return response
    except Exception as e:
        logger.error("Failed to download brand asset %s: %s", path, e)
        return None


def delete_brand_asset(
    user_id: str,
    asset_id: str,
    filename: str
) -> bool:
    """
    Delete a brand asset file from storage.

    Args:
        user_id: The user UUID
        asset_id: The brand asset UUID
        filename: Asset filename

    Returns:
        True if successful
    """
    client = _get_client()
    path = _build_brand_path(user_id, asset_id, filename)

    try:
        client.storage.from_(BUCKET_BRAND_ASSETS).remove([path])
        return True
    except Exception as e:
        logger.error("Failed to delete brand asset %s: %s", path, e)
        return False


def get_brand_asset_url(
    user_id: str,
    asset_id: str,
    filename: str,
    expires_in: int = 3600
) -> Optional[str]:
    """
    Get a signed URL for a brand asset (for private bucket access).

    Args:
        user_id: The user UUID
        asset_id: The brand asset UUID
        filename: Asset filename
        expires_in: URL expiration time in seconds (default 1 hour)

    Returns:
        Signed URL or None
    """
    client = _get_client()
    path = _build_brand_path(user_id, asset_id, filename)

    try:
        response = client.storage.from_(BUCKET_BRAND_ASSETS).create_signed_url(path, expires_in)
        return response.get("signedURL")
    except Exception as e:
        logger.error("Failed to get brand asset signed URL for %s: %s", path, e)
        return None


def delete_user_brand_assets(user_id: str) -> bool:
    """
    Delete all brand assets for a user.

    Educational Note: Uses iterative folder scanning because Supabase .list()
    only returns immediate children. Folders have id=None, files have a UUID id.

    Args:
        user_id: The user UUID

    Returns:
        True if successful
    """
    client = _get_client()
    root_prefix = f"{user_id}/brand"

    try:
        # Iteratively scan folders to collect all file paths
        folders_to_scan = [root_prefix]
        all_paths = []

        while folders_to_scan:
            folder = folders_to_scan.pop()
            entries = client.storage.from_(BUCKET_BRAND_ASSETS).list(
                folder, options=_LIST_OPTIONS
            )
            if not entries:
                continue
            for entry in entries:
                path = f"{folder}/{entry['name']}"
                if entry.get("id") is None:
                    # No id means it's a folder — recurse into it
                    folders_to_scan.append(path)
                else:
                    all_paths.append(path)

        if all_paths:
            client.storage.from_(BUCKET_BRAND_ASSETS).remove(all_paths)
        return True
    except Exception as e:
        logger.error("Failed to delete brand assets for user %s: %s", user_id, e)
        return False
