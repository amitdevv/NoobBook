"""
Jira Processor - Handles JIRA source processing.

Educational Note: Unlike Freshdesk which syncs ticket data locally, the Jira
processor is lightweight. It only verifies the Jira API connection, fetches a
list of available projects for the summary, and marks the source ready.
All actual Jira queries happen live via the chat tools (jira_list_projects,
jira_search_issues, jira_get_issue, jira_get_project).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app.services.ai_services.summary_service import summary_service
from app.services.integrations.knowledge_bases.jira.jira_service import jira_service
from app.services.integrations.supabase import storage_service

logger = logging.getLogger(__name__)


def _build_processed_text(
    source_name: str,
    captured_at: str,
    project_count: int,
    project_names: list[str],
) -> str:
    """
    Build processed text summary of the connected Jira instance.

    Educational Note: This text is stored in the processed-files bucket
    and displayed in the Sources UI as a quick overview. It also feeds
    the AI summary generation so chat knows what Jira data is available.
    """
    header_lines = [
        f"# Extracted from JIRA source: {source_name}",
        "# Type: JIRA",
        f"# Captured at: {captured_at}",
        "# ---",
        "",
    ]

    lines = [
        "## Jira Connection Summary",
        "",
        f"Total projects accessible: {project_count}",
        "",
    ]

    if project_names:
        lines.append("### Available Projects")
        for name in project_names[:20]:  # Cap at 20 for readability
            lines.append(f"- {name}")
        if project_count > 20:
            lines.append(f"- ... and {project_count - 20} more")
        lines.append("")

    lines.append(
        "Tip: Use jira_list_projects, jira_search_issues, jira_get_issue, "
        "and jira_get_project tools in chat for live Jira queries."
    )
    lines.append("")

    return "\n".join(header_lines + lines)


def process_jira(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service,
) -> Dict[str, Any]:
    """
    Process a JIRA source:
    1) Verify Jira API connection by listing projects
    2) Build processed text summary of available projects
    3) Generate AI summary
    4) Mark source ready (skip embedding — queries go through live API tools)
    """
    captured_at = datetime.now().isoformat()
    embedding_info = source.get("embedding_info", {}) or {}

    # Step 1: Verify connection and get project list
    try:
        result = jira_service.list_projects()
    except Exception as e:
        source_service.update_source(
            project_id, source_id, status="error",
            processing_info={"error": f"Failed to connect to Jira: {str(e)}"},
        )
        return {"success": False, "error": str(e)}

    if not result.get("success"):
        error_msg = result.get("error", "Failed to connect to Jira API")
        source_service.update_source(
            project_id, source_id, status="error",
            processing_info={"error": error_msg},
        )
        return {"success": False, "error": error_msg}

    projects = result.get("projects", [])
    project_count = result.get("total", len(projects))
    project_names = [
        f"{p.get('key', '?')} - {p.get('name', 'Unnamed')}"
        for p in projects
    ]

    # Step 2: Build processed text
    processed_text = _build_processed_text(
        source_name=source.get("name", "Jira Projects"),
        captured_at=captured_at,
        project_count=project_count,
        project_names=project_names,
    )

    # Upload processed text to storage
    processed_path = storage_service.upload_processed_file(
        project_id=project_id,
        source_id=source_id,
        content=processed_text,
    )
    if not processed_path:
        source_service.update_source(
            project_id, source_id, status="error",
            processing_info={"error": "Failed to upload processed summary"},
        )
        return {"success": False, "error": "Failed to upload processed file"}

    processing_info = {
        "processor": "jira_connection_verify",
        "captured_at": captured_at,
        "projects_found": project_count,
    }

    # Skip embedding — Jira sources are queried via live API tools, not RAG
    merged_embedding_info = {
        **embedding_info,
        "is_embedded": False,
        "file_extension": ".jira",
    }

    # Step 3: Generate AI summary
    summary_info: Dict[str, Any] = {}
    try:
        summary_source_metadata = {
            "name": source.get("name", "Jira Projects"),
            "category": "jira",
            "file_extension": ".jira",
            "embedding_info": merged_embedding_info,
            "processing_info": {
                **processing_info,
                "total_pages": max(1, project_count),
            },
        }
        summary_info = (
            summary_service.generate_summary(
                project_id, source_id, summary_source_metadata
            )
            or {}
        )
    except Exception as e:
        logger.exception("Summary generation failed for source %s", source_id)
        summary_info = {}

    # Step 4: Mark ready
    source_service.update_source(
        project_id,
        source_id,
        status="ready",
        processing_info=processing_info,
        embedding_info=merged_embedding_info,
        summary_info=summary_info if summary_info else None,
    )

    return {"success": True, "status": "ready"}
