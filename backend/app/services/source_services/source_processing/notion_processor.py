"""
Notion Processor - Fetches Notion page or database content and embeds it.

Educational Note: Notion sources are stored as `.notion` stub files holding
the picked page/database ID. The processor:

1. Reads the stub → gets notion_id + object_type
2. Page sources: fetches the page (recursively walks child blocks) and emits
   it as a single processed page.
3. Database sources: queries the DB (paginated), then fetches each row's
   page as its own processed page. The first page is a header summarizing
   the database schema.
4. Formats everything via build_processed_output() with NOTION page markers
5. Uploads processed text to Supabase Storage
6. Runs the standard embedding + summary flow (Notion content IS embedded,
   unlike live-API integrations like Jira/Mixpanel)

Cooperative cancellation is checked between Notion API calls so a long
database import can be cancelled cleanly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.services.ai_services.embedding_service import embedding_service
from app.services.ai_services.summary_service import summary_service
from app.services.background_services import task_service
from app.services.integrations.knowledge_bases.notion.notion_service import notion_service
from app.services.integrations.supabase import storage_service
from app.utils.embedding_utils import count_tokens, needs_embedding
from app.utils.text import build_processed_output

logger = logging.getLogger(__name__)


class _Cancelled(Exception):
    """Raised when the user cancels processing mid-fetch."""


def _check_cancel(source_id: str) -> None:
    if task_service.is_target_cancelled(source_id):
        raise _Cancelled()


def _fetch_page(source_id: str, notion_id: str) -> Tuple[str, Dict[str, Any]]:
    """
    Fetch a single Notion page. Returns (rendered_text, page_meta).
    Raises ValueError on Notion errors.
    """
    _check_cancel(source_id)
    result = notion_service.get_page(notion_id)
    if not result.get("success"):
        raise ValueError(result.get("error", "Failed to fetch Notion page"))
    page = result["page"]
    title = page.get("title") or "Untitled"
    body = page.get("content") or ""
    text = f"# {title}\n\n{body}" if body else f"# {title}"
    return text, page


def _format_db_row(row: Dict[str, Any], row_body: str) -> str:
    """
    Render a database row as a single processed page: a property table on top,
    followed by the row's page content (the body).
    """
    props = row.get("properties") or {}
    title_value = ""
    other_props: List[Tuple[str, Any]] = []
    for k, v in props.items():
        if isinstance(v, str) and v and not title_value:
            # Promote the first non-empty string property to the H1 title
            # and *skip* re-emitting it in the Properties list below — otherwise
            # the row's title would appear twice in every embedded page.
            title_value = v
            continue
        other_props.append((k, v))

    header = f"# {title_value}" if title_value else "# (untitled row)"
    lines = [header, ""]
    if other_props:
        lines.append("## Properties")
        for k, v in other_props:
            if v in (None, "", [], {}):
                continue
            if isinstance(v, list):
                v_str = ", ".join(str(x) for x in v if x is not None)
            else:
                v_str = str(v)
            lines.append(f"- **{k}**: {v_str}")
        lines.append("")
    if row_body:
        lines.append("## Content")
        lines.append("")
        lines.append(row_body)
    return "\n".join(lines).rstrip()


def _fetch_database_pages(
    source_id: str,
    database_id: str,
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Fetch a Notion database: schema + every row's page. Returns (pages, meta).
    The first page is a database overview; each subsequent page is one row.
    """
    _check_cancel(source_id)
    db_result = notion_service.get_database(database_id)
    if not db_result.get("success"):
        raise ValueError(db_result.get("error", "Failed to fetch Notion database"))
    db = db_result["database"]

    _check_cancel(source_id)
    q_result = notion_service.query_database(database_id, limit=100)
    if not q_result.get("success"):
        raise ValueError(q_result.get("error", "Failed to query Notion database"))
    rows = q_result.get("results", []) or []

    # Page 1: database overview
    schema = db.get("schema") or {}
    overview_lines = [
        f"# Database: {db.get('title', 'Untitled')}",
        "",
        f"Rows fetched: {len(rows)}",
        "",
        "## Schema",
    ]
    for prop_name, prop_meta in schema.items():
        overview_lines.append(f"- **{prop_name}** ({prop_meta.get('type', 'unknown')})")
    overview = "\n".join(overview_lines)

    pages: List[str] = [overview]

    for row in rows:
        _check_cancel(source_id)
        row_id = row.get("id")
        row_body = ""
        if row_id:
            page_result = notion_service.get_page(row_id)
            if page_result.get("success"):
                row_body = (page_result["page"].get("content") or "").strip()
            else:
                # Don't abort the whole import on a single row failure
                logger.warning(
                    "Failed to fetch Notion row %s: %s",
                    row_id,
                    page_result.get("error"),
                )
        pages.append(_format_db_row(row, row_body))

    meta = {
        "title": db.get("title", "Untitled"),
        "notion_url": db.get("url", ""),
        "last_edited_time": db.get("last_edited_time", ""),
        "row_count": len(rows),
    }
    return pages, meta


def process_notion(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service: Any,
) -> Dict[str, Any]:
    """
    Process a Notion source by fetching live content and embedding it.
    """
    # Read the stub
    try:
        with open(raw_file_path, "r", encoding="utf-8") as f:
            stub = json.load(f)
    except Exception as e:
        source_service.update_source(
            project_id, source_id, status="error",
            processing_info={"error": f"Failed to read Notion stub: {e}"},
        )
        return {"success": False, "error": str(e)}

    notion_id = stub.get("notion_id")
    object_type = stub.get("object_type")
    if not notion_id or object_type not in ("page", "database"):
        msg = "Notion stub is missing notion_id or has invalid object_type"
        source_service.update_source(
            project_id, source_id, status="error",
            processing_info={"error": msg},
        )
        return {"success": False, "error": msg}

    if not notion_service.is_configured():
        msg = "Notion is not configured (NOTION_API_KEY missing)"
        source_service.update_source(
            project_id, source_id, status="error",
            processing_info={"error": msg},
        )
        return {"success": False, "error": msg}

    try:
        if object_type == "page":
            text, page_meta = _fetch_page(source_id, notion_id)
            pages = [text]
            metadata = {
                "object_type": "page",
                "notion_url": page_meta.get("url", stub.get("notion_url", "")),
                "last_edited_time": page_meta.get(
                    "last_edited_time", stub.get("last_edited_time", "")
                ),
                "page_count": 1,
            }
            display_title = page_meta.get("title") or stub.get("title") or source.get("name") or "Notion page"
        else:
            pages, db_meta = _fetch_database_pages(source_id, notion_id)
            metadata = {
                "object_type": "database",
                "notion_url": db_meta.get("notion_url", stub.get("notion_url", "")),
                "last_edited_time": db_meta.get(
                    "last_edited_time", stub.get("last_edited_time", "")
                ),
                "page_count": len(pages),
            }
            display_title = db_meta.get("title") or stub.get("title") or source.get("name") or "Notion database"
    except _Cancelled:
        logger.info("Notion processing cancelled for source %s", source_id)
        # Status will be reset by cancel_processing; just return without
        # marking as error.
        return {"success": False, "cancelled": True}
    except ValueError as e:
        source_service.update_source(
            project_id, source_id, status="error",
            processing_info={"error": str(e)},
        )
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.exception("Notion processing failed for source %s", source_id)
        source_service.update_source(
            project_id, source_id, status="error",
            processing_info={"error": str(e)},
        )
        return {"success": False, "error": str(e)}

    # Compute total character + token counts across all pages
    combined = "\n\n".join(pages)
    metadata["character_count"] = len(combined)
    metadata["token_count"] = count_tokens(combined)

    source_name = source.get("name") or display_title
    processed_content = build_processed_output(
        pages=pages,
        source_type="NOTION",
        source_name=source_name,
        metadata=metadata,
    )

    storage_path = storage_service.upload_processed_file(
        project_id=project_id,
        source_id=source_id,
        content=processed_content,
    )
    if not storage_path:
        source_service.update_source(
            project_id, source_id, status="error",
            processing_info={"error": "Failed to upload processed Notion content"},
        )
        return {"success": False, "error": "Failed to upload processed content to storage"}

    processing_info = {
        "processor": "notion",
        "object_type": object_type,
        "notion_id": notion_id,
        "notion_url": metadata.get("notion_url"),
        "total_pages": len(pages),
        "character_count": metadata["character_count"],
    }

    # Embed (Notion content is text-only knowledge — always embed)
    embedding_info: Dict[str, Any]
    try:
        _, _, reason = needs_embedding(text=processed_content)
        source_service.update_source(project_id, source_id, status="embedding")
        logger.info("Starting Notion embedding for %s (%s)", source_name, reason)
        embedding_info = embedding_service.process_embeddings(
            project_id=project_id,
            source_id=source_id,
            source_name=source_name,
            processed_text=processed_content,
        )
    except Exception as e:
        logger.exception("Notion embedding failed for source %s", source_id)
        embedding_info = {
            "is_embedded": False,
            "embedded_at": None,
            "token_count": 0,
            "chunk_count": 0,
            "reason": f"Embedding error: {e}",
        }

    # Carry stub identifiers forward so the chat layer can still tell which
    # Notion ID this source came from after processing.
    embedding_info = {
        **(source.get("embedding_info") or {}),
        **embedding_info,
        "file_extension": ".notion",
        "source_type": "notion",
        "notion_id": notion_id,
        "object_type": object_type,
    }

    # Summary
    summary_info: Dict[str, Any] = {}
    try:
        result = summary_service.generate_summary(
            project_id=project_id,
            source_id=source_id,
            source_metadata={
                **source,
                "processing_info": processing_info,
                "embedding_info": embedding_info,
            },
        )
        if result:
            summary_info = result
    except Exception:
        logger.exception("Summary generation failed for Notion source %s", source_id)

    source_service.update_source(
        project_id,
        source_id,
        status="ready",
        active=True,
        processing_info=processing_info,
        embedding_info=embedding_info,
        summary_info=summary_info if summary_info else None,
    )

    return {"success": True, "status": "ready"}
