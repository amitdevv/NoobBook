"""
Project Fork Service — full-project cloning for share viewers.

When a viewer clicks "Make a copy in your workspace" on a shared project,
we clone the entire project into the viewer's account: sources (raw +
processed files + chunks), chats + messages, and Pinecone vectors. The
viewer ends up with an editable, fully self-contained copy.

What we copy
------------
• Project row     — name (with " (copy)" suffix if needed), description,
                    custom_prompt. Costs/memory reset.
• Sources         — every active source. New UUIDs everywhere; storage
                    files copied; embedding_info paths rewritten.
• Chunks          — text in storage and `chunks` table, with new chunk_ids.
• Pinecone        — vectors fetched from the source namespace and re-upserted
                    into the target namespace under the new ids. No re-embed
                    cost — the viewer "inherits" embeddings the owner paid for.
• Chats / messages— preserved in chronological order; citations are
                    rewritten so [[cite:OLD]] markers in messages point at
                    the new chunk_ids.

What we do NOT copy
-------------------
• Owner-private state: brand assets, API keys, project memory, Google
  Drive tokens, settings_overrides.
• `studio_signals` rows: they're contextual to a chat run and would need
  source_id remapping, but they're not load-bearing for read-back.
• `costs`: viewer starts at zero.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.services.integrations.pinecone.pinecone_service import pinecone_service
from app.services.integrations.supabase import get_supabase, storage_service
from app.services.source_services import source_index_service
from app.utils.citation_utils import parse_chunk_id

logger = logging.getLogger(__name__)


# Citation marker pattern: [[cite:CHUNK_ID]] — matches the format
# documented in citation_utils.py.
_CITE_RE = re.compile(r"\[\[cite:([^\]]+)\]\]")


# ---------------------------------------------------------------------------
# Citation / chunk-id remapping
# ---------------------------------------------------------------------------

def _remap_chunk_id(old_chunk_id: str, source_id_map: Dict[str, str]) -> str:
    """
    Return a chunk_id pointing at the cloned source, or the original if
    we can't remap (parser miss or source not in map). Returning the
    original keeps message text intact even if a citation breaks.
    """
    parsed = parse_chunk_id(old_chunk_id)
    if not parsed:
        return old_chunk_id
    new_source_id = source_id_map.get(parsed["source_id"])
    if not new_source_id:
        return old_chunk_id
    return f"{new_source_id}_page_{parsed['page_number']}_chunk_{parsed['chunk_index']}"


def _rewrite_citations_in_text(text: str, source_id_map: Dict[str, str]) -> str:
    if not text or "[[cite:" not in text:
        return text

    def _sub(match: "re.Match[str]") -> str:
        return f"[[cite:{_remap_chunk_id(match.group(1), source_id_map)}]]"

    return _CITE_RE.sub(_sub, text)


def _rewrite_message_content(content: Any, source_id_map: Dict[str, str]) -> Any:
    """
    Walk a message's content (string, list of blocks, or {text: "..."} dict)
    and rewrite [[cite:OLD]] markers in any nested text. Anything we don't
    recognise is returned unchanged so we don't accidentally drop tool_use
    or tool_result blocks.
    """
    if isinstance(content, str):
        return _rewrite_citations_in_text(content, source_id_map)

    if isinstance(content, dict):
        # Common shape: {"text": "..."} or {"type": "text", "text": "..."}.
        new_dict = dict(content)
        if isinstance(new_dict.get("text"), str):
            new_dict["text"] = _rewrite_citations_in_text(new_dict["text"], source_id_map)
        return new_dict

    if isinstance(content, list):
        return [_rewrite_message_content(block, source_id_map) for block in content]

    return content


# ---------------------------------------------------------------------------
# Source cloning helpers
# ---------------------------------------------------------------------------

def _copy_source_files(
    old_project_id: str,
    old_source_id: str,
    new_project_id: str,
    new_source_id: str,
    source_row: Dict[str, Any],
) -> Tuple[Optional[str], Optional[str]]:
    """
    Copy the raw + processed files from the source's storage paths to the
    cloned project's paths. Returns (new_raw_path, new_processed_path);
    either may be None if the source doesn't have that asset (e.g. a
    pasted-text source has no raw file).
    """
    new_raw_path: Optional[str] = None
    new_processed_path: Optional[str] = None

    embedding_info = source_row.get("embedding_info") or {}
    stored_filename = embedding_info.get("stored_filename") or embedding_info.get("original_filename")
    mime_type = embedding_info.get("mime_type") or "application/octet-stream"

    if stored_filename:
        try:
            raw_bytes = storage_service.download_raw_file(
                old_project_id, old_source_id, stored_filename
            )
        except Exception as exc:
            logger.warning("Fork: failed to download raw file for source %s: %s", old_source_id, exc)
            raw_bytes = None
        if raw_bytes:
            new_raw_path = storage_service.upload_raw_file(
                project_id=new_project_id,
                source_id=new_source_id,
                filename=stored_filename,
                file_data=raw_bytes,
                content_type=mime_type,
            )

    # Processed file is optional — pure-text sources may skip processing.
    try:
        processed_text = storage_service.download_processed_file(old_project_id, old_source_id)
    except Exception as exc:
        logger.warning("Fork: failed to download processed file for source %s: %s", old_source_id, exc)
        processed_text = None

    if processed_text:
        new_processed_path = storage_service.upload_processed_file(
            new_project_id, new_source_id, processed_text
        )

    return new_raw_path, new_processed_path


def _copy_source_chunks(
    old_project_id: str,
    old_source_id: str,
    new_project_id: str,
    new_source_id: str,
    chunk_id_map: Dict[str, str],
) -> List[Tuple[str, str, Dict[str, Any]]]:
    """
    Copy chunk text files from old to new storage paths and populate
    `chunk_id_map` in place. Returns a list of (old_chunk_id, new_chunk_id,
    chunk_meta) tuples — meta carries page number / source_id so the
    chunks-table writer below has everything it needs.
    """
    try:
        chunks = storage_service.list_source_chunks(old_project_id, old_source_id)
    except Exception as exc:
        logger.warning("Fork: list_source_chunks failed for %s: %s", old_source_id, exc)
        return []

    pairs: List[Tuple[str, str, Dict[str, Any]]] = []
    for chunk in chunks or []:
        old_chunk_id = chunk.get("chunk_id")
        if not old_chunk_id:
            continue
        parsed = parse_chunk_id(old_chunk_id)
        if not parsed:
            logger.warning("Fork: skipping unparseable chunk_id %s", old_chunk_id)
            continue
        new_chunk_id = (
            f"{new_source_id}_page_{parsed['page_number']}_chunk_{parsed['chunk_index']}"
        )
        chunk_id_map[old_chunk_id] = new_chunk_id

        text = chunk.get("text") or ""
        if not text:
            # Try one explicit download in case `list_source_chunks` shapes
            # change in future and stop returning text inline.
            text = storage_service.download_chunk(old_project_id, old_source_id, old_chunk_id) or ""

        if text:
            storage_service.upload_chunk(
                project_id=new_project_id,
                source_id=new_source_id,
                chunk_id=new_chunk_id,
                content=text,
            )

        pairs.append((old_chunk_id, new_chunk_id, {
            "page_number": parsed["page_number"],
            "chunk_index": parsed["chunk_index"],
            "text": text,
        }))

    return pairs


def _insert_chunks_table_rows(
    new_source_id: str,
    pairs: List[Tuple[str, str, Dict[str, Any]]],
) -> None:
    """
    Mirror the cloned chunks into the `chunks` Postgres table so any
    code path that joins on it keeps working.
    """
    if not pairs:
        return
    client = get_supabase()
    rows = []
    for _old_id, new_id, meta in pairs:
        rows.append({
            "id": new_id,
            "source_id": new_source_id,
            "content": meta.get("text") or "",
            "page_number": meta.get("page_number"),
            "chunk_number": meta.get("chunk_index"),
        })
    try:
        client.table("chunks").insert(rows).execute()
    except Exception as exc:
        # Non-fatal: storage chunks are the source of truth for citations,
        # the table is a convenience join. Log and move on.
        logger.warning("Fork: chunks-table insert failed for source %s: %s", new_source_id, exc)


def _copy_pinecone_vectors(
    old_namespace: str,
    new_namespace: str,
    chunk_id_map: Dict[str, str],
    source_id_map: Dict[str, str],
) -> int:
    """
    Fetch vectors from the source namespace and re-upsert under new ids
    in the target namespace, with metadata.source_id rewritten so the
    semantic-search filters on the new project still resolve.

    Returns the number of vectors copied. Vectors that don't come back
    from `fetch_vectors_by_ids` (e.g. tiny sources that bypassed
    embedding) are silently skipped.
    """
    if not chunk_id_map:
        return 0

    if not pinecone_service.is_configured():
        logger.info("Fork: Pinecone not configured; skipping vector copy")
        return 0

    try:
        fetched = pinecone_service.fetch_vectors_by_ids(
            list(chunk_id_map.keys()), namespace=old_namespace
        )
    except Exception as exc:
        logger.warning("Fork: Pinecone fetch failed: %s", exc)
        return 0

    new_vectors: List[Dict[str, Any]] = []
    for old_chunk_id, vec in fetched.items():
        new_chunk_id = chunk_id_map.get(old_chunk_id)
        if not new_chunk_id:
            continue
        meta = dict(vec.get("metadata") or {})
        old_source_id = meta.get("source_id")
        if old_source_id and old_source_id in source_id_map:
            meta["source_id"] = source_id_map[old_source_id]
        # Ensure the chunk_id stored inside metadata also points at the
        # cloned chunk — some search paths read from metadata directly.
        meta["chunk_id"] = new_chunk_id
        new_vectors.append({
            "id": new_chunk_id,
            "values": vec["values"],
            "metadata": meta,
        })

    if not new_vectors:
        return 0

    try:
        result = pinecone_service.upsert_vectors(new_vectors, namespace=new_namespace)
        return result.get("upserted_count", 0)
    except Exception as exc:
        logger.warning("Fork: Pinecone upsert failed: %s", exc)
        return 0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _unique_project_name(client, target_user_id: str, base_name: str) -> str:
    """
    Append " (copy)" / " (copy 2)" / ... until the name is unique for
    this user. The DB has a unique-name-per-user check, so we resolve
    collisions in code rather than catching the exception.
    """
    suffix = 0
    candidate = base_name
    while True:
        existing = (
            client.table("projects")
            .select("id")
            .eq("user_id", target_user_id)
            .ilike("name", candidate)
            .limit(1)
            .execute()
        )
        if not existing.data:
            return candidate
        suffix += 1
        candidate = f"{base_name} (copy)" if suffix == 1 else f"{base_name} (copy {suffix})"


def fork_project(
    source_project_id: str,
    source_owner_user_id: str,
    target_user_id: str,
    seed_chat_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Clone an entire project for ``target_user_id``.

    Args:
        source_project_id: Project being copied (the owner's).
        source_owner_user_id: For provenance — stored in
            ``forked_from_user_id`` so the UI can render "Forked from
            <owner>'s workspace".
        target_user_id: The viewer creating the fork. They become the
            sole owner of the new project.
        seed_chat_id: Optional — id of the chat the viewer was reading
            when they triggered the fork. Returned alongside the new
            project so the frontend can deep-link them straight to the
            cloned chat.

    Returns:
        Dict with at least ``project_id`` and (optionally) ``chat_id``,
        or None if the source project cannot be read.
    """
    client = get_supabase()

    # Read source project. We don't filter by user_id here — the share
    # decorator has already authorized this caller; the project's owner
    # is `source_owner_user_id` and may differ from the viewer.
    src_resp = (
        client.table("projects")
        .select("*")
        .eq("id", source_project_id)
        .limit(1)
        .execute()
    )
    if not src_resp.data:
        logger.warning("Fork: source project %s not found", source_project_id)
        return None
    src = src_resp.data[0]

    base_name = (src.get("name") or "Shared project").strip() or "Shared project"
    new_name = _unique_project_name(client, target_user_id, f"{base_name} (copy)")

    project_row = {
        "user_id": target_user_id,
        "name": new_name,
        "description": src.get("description") or "",
        # Carry custom_prompt — it's a project-level instruction, not
        # owner-private state. Memory + costs are reset.
        "custom_prompt": src.get("custom_prompt"),
        "memory": {},
        "costs": {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": 0,
            "by_model": {},
        },
        "forked_from_project_id": source_project_id,
        "forked_from_user_id": source_owner_user_id,
    }
    new_proj_resp = client.table("projects").insert(project_row).execute()
    if not new_proj_resp.data:
        logger.error("Fork: failed to insert cloned project for user %s", target_user_id)
        return None
    new_project = new_proj_resp.data[0]
    new_project_id = new_project["id"]

    # ── Sources + chunks ────────────────────────────────────────────
    source_id_map: Dict[str, str] = {}
    chunk_id_map: Dict[str, str] = {}

    sources = source_index_service.list_sources_from_index(source_project_id)
    for src_row in sources or []:
        old_source_id = src_row.get("id")
        if not old_source_id:
            continue
        new_source_id = str(uuid.uuid4())
        source_id_map[old_source_id] = new_source_id

        new_raw_path, new_processed_path = _copy_source_files(
            old_project_id=source_project_id,
            old_source_id=old_source_id,
            new_project_id=new_project_id,
            new_source_id=new_source_id,
            source_row=src_row,
        )
        chunk_pairs = _copy_source_chunks(
            old_project_id=source_project_id,
            old_source_id=old_source_id,
            new_project_id=new_project_id,
            new_source_id=new_source_id,
            chunk_id_map=chunk_id_map,
        )

        # Build a fresh source row. We keep status, type, token_count,
        # page_count, file_size, embedding_info — but rewrite paths.
        new_embedding_info = dict(src_row.get("embedding_info") or {})
        # The path-bearing keys point inside the old project; nothing
        # downstream reads "raw_file_path" off embedding_info today, but
        # be defensive in case future code adds it.
        for key in ("raw_file_path", "processed_file_path"):
            new_embedding_info.pop(key, None)

        source_index_service.add_source_to_index(new_project_id, {
            "id": new_source_id,
            "name": src_row.get("name"),
            "description": src_row.get("description"),
            "type": src_row.get("type"),
            "status": src_row.get("status") or "ready",
            "raw_file_path": new_raw_path,
            "processed_file_path": new_processed_path,
            "token_count": src_row.get("token_count"),
            "page_count": src_row.get("page_count"),
            "file_size": src_row.get("file_size"),
            "embedding_info": new_embedding_info,
            "summary_info": src_row.get("summary_info") or {},
            # Reset processing_info — it's transient state from the
            # owner's processing run.
            "processing_info": {},
            "url": src_row.get("url"),
            "is_active": src_row.get("is_active", True),
        })

        _insert_chunks_table_rows(new_source_id, chunk_pairs)

    # ── Pinecone vectors ────────────────────────────────────────────
    copied = _copy_pinecone_vectors(
        old_namespace=source_project_id,
        new_namespace=new_project_id,
        chunk_id_map=chunk_id_map,
        source_id_map=source_id_map,
    )
    logger.info(
        "Fork: copied %d vectors from %s → %s (mapped %d chunks)",
        copied, source_project_id, new_project_id, len(chunk_id_map),
    )

    # ── Chats + messages ────────────────────────────────────────────
    chat_resp = (
        client.table("chats")
        .select("*")
        .eq("project_id", source_project_id)
        .order("created_at", desc=False)
        .execute()
    )
    chat_id_map: Dict[str, str] = {}
    for old_chat in chat_resp.data or []:
        old_chat_id = old_chat.get("id")
        if not old_chat_id:
            continue

        # Remap selected_source_ids onto the cloned source ids; drop any
        # we couldn't map (defensive — shouldn't happen for clean data).
        old_selected = old_chat.get("selected_source_ids") or []
        new_selected = [source_id_map[s] for s in old_selected if s in source_id_map]

        new_chat_row = {
            "project_id": new_project_id,
            "title": old_chat.get("title") or "Untitled chat",
            "selected_source_ids": new_selected,
            "forked_from_chat_id": old_chat_id,
            "forked_from_project_id": source_project_id,
        }
        ins = client.table("chats").insert(new_chat_row).execute()
        if not ins.data:
            logger.warning("Fork: failed to insert chat clone for %s", old_chat_id)
            continue
        new_chat_id = ins.data[0]["id"]
        chat_id_map[old_chat_id] = new_chat_id

        # Messages — chronological, citations rewritten.
        msg_resp = (
            client.table("messages")
            .select("role, content, citations, model, tokens_input, tokens_output, cost_usd, created_at")
            .eq("chat_id", old_chat_id)
            .order("created_at", desc=False)
            .execute()
        )
        message_rows = []
        for msg in msg_resp.data or []:
            old_citations = msg.get("citations") or []
            new_citations = [_remap_chunk_id(c, source_id_map) for c in old_citations]
            message_rows.append({
                "chat_id": new_chat_id,
                "role": msg.get("role"),
                "content": _rewrite_message_content(msg.get("content"), source_id_map),
                "citations": new_citations,
                "model": msg.get("model"),
                "tokens_input": msg.get("tokens_input"),
                "tokens_output": msg.get("tokens_output"),
                "cost_usd": msg.get("cost_usd"),
            })
        if message_rows:
            try:
                client.table("messages").insert(message_rows).execute()
            except Exception as exc:
                logger.warning("Fork: bulk message insert failed for chat %s: %s", new_chat_id, exc)

    # Map the seed chat (the one the viewer was reading) to its clone so
    # the frontend can redirect straight to it.
    new_seed_chat_id = chat_id_map.get(seed_chat_id) if seed_chat_id else None

    return {
        "project_id": new_project_id,
        "project_name": new_project["name"],
        "chat_id": new_seed_chat_id,
        "source_count": len(source_id_map),
        "chat_count": len(chat_id_map),
    }
