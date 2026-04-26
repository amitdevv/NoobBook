"""
Partial-image streaming helper for studio surfaces.

GPT Image 2 streams partial frames while the final image renders. This
helper builds the `on_partial(b64_json, idx)` callback that each studio
service passes to imagen_service: it decodes the partial bytes, uploads
them to Supabase, and appends the URL to the job's `partial_images`
list so the frontend can poll-and-render a live preview.

Per-surface URL/filename patterns differ (e.g. email's serve route
extracts the job_id from the filename instead of the path), so callers
provide `filename_builder(idx) -> filename` and `url_builder(filename) ->
url` closures. Failures are logged and swallowed — a missed partial
must never break the actual image generation.
"""
import base64
import logging
from typing import Callable

from app.services.integrations.supabase import storage_service
from app.services.studio_services import studio_index_service

logger = logging.getLogger(__name__)


def make_partial_callback(
    project_id: str,
    job_id: str,
    storage_kind: str,
    filename_builder: Callable[[int], str],
    url_builder: Callable[[str], str],
) -> Callable[[str, int], None]:
    """
    Return an on_partial(b64_json, idx) callback.

    Args:
        project_id: Project UUID.
        job_id: Studio job UUID.
        storage_kind: storage_service.upload_studio_binary `job_type` arg.
        filename_builder: idx -> filename. Each call site decides whether
            to embed job_id, label (e.g. "hero", "linkedin"), etc.
        url_builder: filename -> URL the frontend should fetch the partial
            from. Mirrors the per-surface URL pattern the existing final
            image uses.
    """
    def on_partial(b64_json: str, idx: int) -> None:
        try:
            partial_bytes = base64.b64decode(b64_json)
        except Exception:
            logger.exception("Failed to decode partial image b64")
            return

        filename = filename_builder(idx)

        storage_path = storage_service.upload_studio_binary(
            project_id=project_id,
            job_type=storage_kind,
            job_id=job_id,
            filename=filename,
            file_data=partial_bytes,
            content_type="image/png",
        )
        if not storage_path:
            logger.warning("Partial image upload returned no path (job=%s)", job_id)
            return

        url = url_builder(filename)
        try:
            studio_index_service.append_partial_image(project_id, job_id, url)
        except Exception:
            logger.exception("Failed to append partial image to job %s", job_id)

    return on_partial
