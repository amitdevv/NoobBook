"""
MCP Processor - Handles MCP source processing (resource snapshot + embedding).

Educational Note: An MCP source is processed by:
1. Reading the `.mcp` raw metadata to get connection_id and resource URIs
2. Connecting to the MCP server and reading the selected resources
3. Building processed text with each resource as a "page"
4. Embedding the content for RAG search (unlike database sources which skip embedding)
5. Generating a summary

This enables:
- Searching MCP resource content via search_sources in chat
- Citations pointing to specific resource content
- Manual refresh via retry (re-snapshots from MCP server)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

from app.services.ai_services.embedding_service import embedding_service
from app.services.ai_services.summary_service import summary_service
from app.services.data_services.mcp_connection_service import mcp_connection_service
from app.services.integrations.supabase import storage_service


def _load_raw_metadata(raw_file_path: Path) -> Dict[str, Any]:
    """Load `.mcp` raw metadata JSON. Raises ValueError on failure."""
    try:
        with open(raw_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ValueError(f"MCP metadata file not found: {raw_file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"MCP metadata file is corrupted: {e}")
    except Exception as e:
        raise ValueError(f"Failed to read MCP metadata: {e}")


def _build_processed_text(
    source_name: str,
    server_url: str,
    captured_at: str,
    resources: List[Dict[str, Any]],
) -> str:
    """
    Build processed text from MCP resource contents.

    Each resource becomes one "page" in the processed output, following the
    standard NoobBook page marker format: === MCP PAGE N of M ===
    """
    total = len(resources)

    header_lines = [
        f"# Extracted from MCP: {source_name}",
        "# Type: MCP",
        f"# Server: {server_url}",
        f"# Resources: {total}",
        f"# Captured at: {captured_at}",
        "# ---",
        "",
    ]

    content_lines: List[str] = []
    for i, resource in enumerate(resources, start=1):
        uri = resource.get("uri", "")
        name = resource.get("name", uri)
        content = resource.get("content", "")

        content_lines.append(f"=== MCP PAGE {i} of {total} ===")
        content_lines.append(f"## Resource: {name}")
        content_lines.append(f"URI: {uri}")
        content_lines.append("")
        content_lines.append(content)
        content_lines.append("")

    return "\n".join(header_lines + content_lines)


def process_mcp(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service,
) -> Dict[str, Any]:
    """
    Process an MCP source:
    1) Load raw metadata (.mcp)
    2) Resolve connection_id -> server URL + auth
    3) Read resources from MCP server
    4) Save processed text to Supabase Storage
    5) Embed content for RAG search
    6) Generate summary
    7) Mark source ready
    """
    captured_at = datetime.now().isoformat()

    embedding_info = source.get("embedding_info", {}) or {}
    try:
        raw_meta = _load_raw_metadata(raw_file_path)
    except ValueError as e:
        error_msg = str(e)
        logger.error("MCP processor: %s (source_id=%s)", error_msg, source_id)
        source_service.update_source(
            project_id, source_id,
            status="error",
            processing_info={"error": error_msg},
        )
        return {"success": False, "error": error_msg}

    connection_id = embedding_info.get("connection_id") or raw_meta.get("connection_id")
    if not connection_id:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "MCP source missing connection_id"},
        )
        return {"success": False, "error": "Missing connection_id"}

    resource_uris = raw_meta.get("resource_uris", [])
    if not resource_uris:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "MCP source has no resource URIs"},
        )
        return {"success": False, "error": "No resource URIs"}

    # Load connection secret from account-level table.
    # Uses _server_internal=True to skip user-level access control —
    # the source was already authorized at upload time.
    logger.info(
        "MCP processor: resolving connection_id=%s (source_id=%s)",
        connection_id, source_id,
    )
    connection = mcp_connection_service.get_connection(
        connection_id=connection_id,
        include_secret=True,
        _server_internal=True,
    )
    if not connection:
        error_msg = (
            f"MCP connection not found (connection_id={connection_id}). "
            f"Verify the connection exists in Settings → MCP Connections."
        )
        logger.error("MCP processor: %s", error_msg)
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": error_msg},
        )
        return {"success": False, "error": error_msg}

    server_url = connection.get("server_url") or ""
    auth_type = connection.get("auth_type", "none")
    auth_config = connection.get("auth_config")
    transport = connection.get("transport", "sse")
    stdio_config = connection.get("stdio_config")

    # Read resources from MCP server
    try:
        from app.services.integrations.mcp.mcp_client import read_resources

        resources = read_resources(
            server_url=server_url,
            auth_type=auth_type,
            auth_config=auth_config,
            resource_uris=resource_uris,
            transport=transport,
            stdio_config=stdio_config,
        )
    except Exception as e:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": f"Failed to read MCP resources: {str(e)}"},
        )
        return {"success": False, "error": str(e)}

    if not resources:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "No resources returned from MCP server"},
        )
        return {"success": False, "error": "No resources returned"}

    processed_text = _build_processed_text(
        source_name=source.get("name", "MCP Resources"),
        server_url=server_url,
        captured_at=captured_at,
        resources=resources,
    )

    # Upload processed text
    processed_path = storage_service.upload_processed_file(
        project_id=project_id,
        source_id=source_id,
        content=processed_text,
    )
    if not processed_path:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "Failed to upload processed MCP content"},
        )
        return {"success": False, "error": "Failed to upload processed file"}

    processing_info = {
        "processor": "mcp_resource_snapshot",
        "captured_at": captured_at,
        "server_url": server_url,
        "resource_count": len(resources),
    }

    # Run embedding pipeline (MCP resources have real content worth searching)
    merged_embedding_info = {
        **embedding_info,
        "connection_id": connection_id,
        "file_extension": ".mcp",
    }

    try:
        source_service.update_source(project_id, source_id, status="embedding")

        embedding_result = embedding_service.process_embeddings(
            project_id=project_id,
            source_id=source_id,
            processed_text=processed_text,
            source_name=source.get("name", "MCP Resources"),
        )
        merged_embedding_info["is_embedded"] = True
        merged_embedding_info["chunk_count"] = embedding_result.get("chunk_count", 0)
        merged_embedding_info["token_count"] = embedding_result.get("token_count", 0)
    except Exception as e:
        logger.exception("Embedding failed for MCP source %s", source_id)
        merged_embedding_info["is_embedded"] = False
        merged_embedding_info["embedding_error"] = str(e)

    # Generate summary
    summary_info: Dict[str, Any] = {}
    try:
        summary_source_metadata = {
            "name": source.get("name", "MCP Resources"),
            "category": "mcp",
            "file_extension": ".mcp",
            "embedding_info": merged_embedding_info,
            "processing_info": {**processing_info, "total_pages": len(resources)},
        }
        summary_info = summary_service.generate_summary(project_id, source_id, summary_source_metadata) or {}
    except Exception as e:
        logger.exception("Summary generation failed for MCP source %s", source_id)
        summary_info = {}

    source_service.update_source(
        project_id,
        source_id,
        status="ready",
        processing_info=processing_info,
        embedding_info=merged_embedding_info,
        summary_info=summary_info if summary_info else None,
    )

    return {"success": True, "status": "ready"}
