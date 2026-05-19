"""
Tests for the Notion source integration: service-level recursion + pagination,
upload stub creation, and the processor's page/database flows.

These tests stub out the Notion HTTP layer (_make_request) and the embedding /
summary / storage pipeline so we exercise the wiring without external calls.
"""
from __future__ import annotations

import os

# Importing source_services pulls in supabase auth_service, which constructs
# a dedicated client at import time and refuses to load without these env vars
# being set. Provide harmless placeholders before any app imports happen.
os.environ.setdefault("SUPABASE_URL", "http://localhost")
# supabase-py validates the key looks like a JWT (3 base64ish segments). Any
# well-formed placeholder will do — we never actually call the real client.
os.environ.setdefault(
    "SUPABASE_SERVICE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoidGVzdCJ9.test",
)

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# notion_service: recursion + block rendering + pagination
# ---------------------------------------------------------------------------


def _make_block(block_type: str, text: str = "", has_children: bool = False, block_id: str = "b1", extra=None) -> dict:
    body = {"rich_text": [{"plain_text": text}]}
    if extra:
        body.update(extra)
    return {
        "id": block_id,
        "type": block_type,
        block_type: body,
        "has_children": has_children,
    }


def test_get_page_recurses_into_toggle_children(monkeypatch):
    """A toggle with nested children should surface those children in content."""
    # The package's __init__.py rebinds the `notion_service` attribute to the
    # singleton, masking the submodule for plain `import … as` resolution.
    # Use importlib to get the actual module object so we can instantiate
    # NotionService directly in tests.
    import importlib
    ns_module = importlib.import_module(
        "app.services.integrations.knowledge_bases.notion.notion_service"
    )
    svc = ns_module.NotionService()
    svc._configured = True
    svc._api_key = "test"

    page_meta = {
        "id": "page-1",
        "url": "https://notion.so/page-1",
        "created_time": "2026-05-01T00:00:00.000Z",
        "last_edited_time": "2026-05-02T00:00:00.000Z",
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": "My Page"}]},
        },
    }
    parent_children = {
        "results": [
            _make_block("paragraph", "Hello world", block_id="b1"),
            _make_block("toggle", "Outer", has_children=True, block_id="toggle-1"),
        ],
        "has_more": False,
    }
    toggle_children = {
        "results": [
            _make_block("paragraph", "Inside the toggle", block_id="b2"),
        ],
        "has_more": False,
    }

    def fake_request(endpoint, method="GET", json_data=None):
        if endpoint.startswith("pages/page-1"):
            return {"success": True, "data": page_meta}
        if endpoint.startswith("blocks/page-1/children"):
            return {"success": True, "data": parent_children}
        if endpoint.startswith("blocks/toggle-1/children"):
            return {"success": True, "data": toggle_children}
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    monkeypatch.setattr(svc, "_make_request", fake_request)

    result = svc.get_page("page-1")
    assert result["success"], result
    content = result["page"]["content"]
    assert "Hello world" in content
    # Toggle marker + nested paragraph (indented one level)
    assert "Outer" in content
    assert "Inside the toggle" in content
    assert result["page"]["title"] == "My Page"


def test_get_page_respects_recursion_cap(monkeypatch):
    """Recursion must stop at MAX_RECURSION_DEPTH so circular pages don't run away."""
    # The package's __init__.py rebinds the `notion_service` attribute to the
    # singleton, masking the submodule for plain `import … as` resolution.
    # Use importlib to get the actual module object so we can instantiate
    # NotionService directly in tests.
    import importlib
    ns_module = importlib.import_module(
        "app.services.integrations.knowledge_bases.notion.notion_service"
    )
    svc = ns_module.NotionService()
    svc._configured = True
    svc._api_key = "test"

    page_meta = {"id": "p", "properties": {}}

    def fake_request(endpoint, method="GET", json_data=None):
        if endpoint.startswith("pages/p"):
            return {"success": True, "data": page_meta}
        # Every block has a child of itself (depth-1 child).
        return {
            "success": True,
            "data": {
                "results": [_make_block("paragraph", "x", has_children=True, block_id="child")],
                "has_more": False,
            },
        }

    monkeypatch.setattr(svc, "_make_request", fake_request)
    result = svc.get_page("p")
    assert result["success"]
    # MAX_RECURSION_DEPTH=5 → top-level call (depth=0) plus 5 recursive layers,
    # each emitting one paragraph block.
    assert result["page"]["block_count"] <= ns_module.MAX_RECURSION_DEPTH + 1


def test_query_database_paginates(monkeypatch):
    """query_database should follow has_more / next_cursor until exhausted."""
    # The package's __init__.py rebinds the `notion_service` attribute to the
    # singleton, masking the submodule for plain `import … as` resolution.
    # Use importlib to get the actual module object so we can instantiate
    # NotionService directly in tests.
    import importlib
    ns_module = importlib.import_module(
        "app.services.integrations.knowledge_bases.notion.notion_service"
    )
    svc = ns_module.NotionService()
    svc._configured = True
    svc._api_key = "test"

    pages = [
        {
            "results": [{"id": f"row-{i}", "properties": {}} for i in range(2)],
            "has_more": True,
            "next_cursor": "cursor-1",
        },
        {
            "results": [{"id": f"row-{i+2}", "properties": {}} for i in range(2)],
            "has_more": True,
            "next_cursor": "cursor-2",
        },
        {
            "results": [{"id": "row-4", "properties": {}}],
            "has_more": False,
        },
    ]
    calls = {"i": 0}

    def fake_request(endpoint, method="GET", json_data=None):
        i = calls["i"]
        calls["i"] += 1
        return {"success": True, "data": pages[i]}

    monkeypatch.setattr(svc, "_make_request", fake_request)
    result = svc.query_database("db-1")
    assert result["success"]
    ids = [r["id"] for r in result["results"]]
    assert ids == ["row-0", "row-1", "row-2", "row-3", "row-4"]


# ---------------------------------------------------------------------------
# notion_upload: stub creation
# ---------------------------------------------------------------------------


def test_add_notion_source_creates_stub(monkeypatch):
    from app.services.source_services.source_upload import notion_upload

    # Pretend Notion is configured
    monkeypatch.setattr(notion_upload.notion_service, "is_configured", lambda: True)
    # Capture the bytes uploaded as raw file
    captured = {}

    def fake_upload_raw(project_id, source_id, filename, file_data, content_type=None):
        captured["filename"] = filename
        captured["file_data"] = file_data
        return f"raw/{project_id}/{source_id}/{filename}"

    monkeypatch.setattr(notion_upload.storage_service, "upload_raw_file", fake_upload_raw)
    monkeypatch.setattr(
        notion_upload.source_index_service, "add_source_to_index", lambda *a, **k: None
    )
    # Don't actually queue work
    monkeypatch.setattr(notion_upload, "_submit_processing_task", lambda *a, **k: None)

    result = notion_upload.add_notion_source(
        project_id="proj-1",
        notion_id="notion-page-1",
        object_type="page",
        title="My Page",
        notion_url="https://notion.so/My-Page",
        last_edited_time="2026-05-19T00:00:00Z",
    )

    assert result["type"] == "NOTION"
    assert result["status"] == "uploaded"
    assert result["embedding_info"]["notion_id"] == "notion-page-1"
    assert result["embedding_info"]["object_type"] == "page"
    assert result["embedding_info"]["file_extension"] == ".notion"
    # Stub bytes are JSON with the right keys
    stub = json.loads(captured["file_data"].decode("utf-8"))
    assert stub["notion_id"] == "notion-page-1"
    assert stub["object_type"] == "page"


def test_add_notion_source_rejects_invalid_object_type(monkeypatch):
    from app.services.source_services.source_upload import notion_upload
    monkeypatch.setattr(notion_upload.notion_service, "is_configured", lambda: True)
    with pytest.raises(ValueError, match="object_type"):
        notion_upload.add_notion_source(
            project_id="p", notion_id="n", object_type="block"
        )


def test_add_notion_source_requires_configured(monkeypatch):
    from app.services.source_services.source_upload import notion_upload
    monkeypatch.setattr(notion_upload.notion_service, "is_configured", lambda: False)
    with pytest.raises(ValueError, match="Notion not configured"):
        notion_upload.add_notion_source(
            project_id="p", notion_id="n", object_type="page"
        )


# ---------------------------------------------------------------------------
# notion_processor: page + database flows
# ---------------------------------------------------------------------------


def _write_stub(tmp_path: Path, notion_id: str, object_type: str) -> Path:
    path = tmp_path / f"{notion_id}.notion"
    path.write_text(json.dumps({
        "kind": "notion_source",
        "notion_id": notion_id,
        "object_type": object_type,
        "title": "T",
        "notion_url": "https://notion.so/T",
        "last_edited_time": "2026-05-01T00:00:00Z",
    }))
    return path


def _patch_processor_pipeline(monkeypatch):
    """Stub out storage / embedding / summary / cancellation so the processor
    only exercises its own logic."""
    from app.services.source_services.source_processing import notion_processor as np_module

    monkeypatch.setattr(np_module.notion_service, "is_configured", lambda: True)
    monkeypatch.setattr(np_module.task_service, "is_target_cancelled", lambda _id: False)
    monkeypatch.setattr(
        np_module.storage_service, "upload_processed_file",
        lambda **kwargs: f"processed/{kwargs['source_id']}.txt",
    )
    monkeypatch.setattr(
        np_module.embedding_service, "process_embeddings",
        lambda **kwargs: {"is_embedded": True, "chunk_count": 3, "token_count": 100},
    )
    monkeypatch.setattr(
        np_module.summary_service, "generate_summary",
        lambda **kwargs: {"summary": "ok"},
    )
    return np_module


def test_process_notion_page(tmp_path, monkeypatch):
    np_module = _patch_processor_pipeline(monkeypatch)

    monkeypatch.setattr(np_module.notion_service, "get_page", lambda nid: {
        "success": True,
        "page": {
            "id": nid,
            "title": "My Page",
            "url": "https://notion.so/My-Page",
            "last_edited_time": "2026-05-02T00:00:00Z",
            "content": "Hello world\n\n## Section\n\nMore",
            "block_count": 3,
        },
    })

    source_service = MagicMock()
    raw_path = _write_stub(tmp_path, "page-1", "page")
    result = np_module.process_notion(
        project_id="proj-1",
        source_id="src-1",
        source={"id": "src-1", "name": "My Page"},
        raw_file_path=raw_path,
        source_service=source_service,
    )

    assert result["success"], result
    assert result["status"] == "ready"
    # Final update_source call must include status=ready
    final_call = source_service.update_source.call_args_list[-1]
    assert final_call.kwargs.get("status") == "ready"


def test_process_notion_database(tmp_path, monkeypatch):
    np_module = _patch_processor_pipeline(monkeypatch)

    monkeypatch.setattr(np_module.notion_service, "get_database", lambda nid: {
        "success": True,
        "database": {
            "id": nid,
            "title": "Tasks",
            "url": "https://notion.so/Tasks",
            "last_edited_time": "2026-05-03T00:00:00Z",
            "schema": {"Name": {"type": "title"}, "Status": {"type": "select"}},
        },
    })
    monkeypatch.setattr(np_module.notion_service, "query_database", lambda nid, **kw: {
        "success": True,
        "results": [
            {"id": "row-1", "title": "Task 1",
             "properties": {"Name": "Task 1", "Status": "Open"}},
            {"id": "row-2", "title": "Task 2",
             "properties": {"Name": "Task 2", "Status": "Done"}},
        ],
    })
    monkeypatch.setattr(np_module.notion_service, "get_page", lambda nid: {
        "success": True,
        "page": {"id": nid, "title": "row body", "content": "Row body for " + nid},
    })

    source_service = MagicMock()
    raw_path = _write_stub(tmp_path, "db-1", "database")
    result = np_module.process_notion(
        project_id="proj-1",
        source_id="src-2",
        source={"id": "src-2", "name": "Tasks"},
        raw_file_path=raw_path,
        source_service=source_service,
    )

    assert result["success"], result
    # 1 overview + 2 row pages
    final_call = source_service.update_source.call_args_list[-1]
    pi = final_call.kwargs.get("processing_info", {})
    assert pi.get("total_pages") == 3


def test_query_database_extracts_title_from_title_property(monkeypatch):
    """The row's title must come from the title-type property, not from
    whichever string-valued property happens to come first."""
    import importlib
    ns_module = importlib.import_module(
        "app.services.integrations.knowledge_bases.notion.notion_service"
    )
    svc = ns_module.NotionService()
    svc._configured = True
    svc._api_key = "test"

    # A row where a URL column comes BEFORE the title column in property order
    # — the formatted props would otherwise collapse to indistinguishable
    # strings and the URL would get promoted as the row heading.
    row = {
        "id": "row-1",
        "properties": {
            "Link": {"type": "url", "url": "https://example.com"},
            "Name": {"type": "title", "title": [{"plain_text": "Real Title"}]},
            "Status": {"type": "select", "select": {"name": "Open"}},
        },
    }
    monkeypatch.setattr(svc, "_make_request", lambda *a, **kw: {
        "success": True,
        "data": {"results": [row], "has_more": False},
    })

    result = svc.query_database("db-1")
    assert result["success"]
    assert result["results"][0]["title"] == "Real Title"


def test_query_database_early_exits_at_limit(monkeypatch):
    """Pagination must stop once `limit` rows are collected — no over-fetching."""
    import importlib
    ns_module = importlib.import_module(
        "app.services.integrations.knowledge_bases.notion.notion_service"
    )
    svc = ns_module.NotionService()
    svc._configured = True
    svc._api_key = "test"

    calls = {"n": 0}

    def fake_request(endpoint, method="GET", json_data=None):
        calls["n"] += 1
        # Each page returns 50 rows and claims there's more — but the caller
        # asked for limit=50, so the loop must break after the first page.
        return {
            "success": True,
            "data": {
                "results": [
                    {"id": f"row-{i}", "title": "t", "properties": {}}
                    for i in range(50)
                ],
                "has_more": True,
                "next_cursor": "cursor-x",
            },
        }

    monkeypatch.setattr(svc, "_make_request", fake_request)
    result = svc.query_database("db-1", limit=50)
    assert result["success"]
    assert len(result["results"]) == 50
    assert calls["n"] == 1, "should not have requested a second page"


def test_format_db_row_uses_title_field(monkeypatch):
    """_format_db_row should honour the explicit `title` field, even if a
    different string-valued property comes earlier."""
    from app.services.source_services.source_processing.notion_processor import (
        _format_db_row,
    )
    row = {
        "id": "r",
        "title": "Real Title",
        "properties": {
            "Link": "https://example.com",
            "Name": "Real Title",
            "Status": "Open",
        },
    }
    rendered = _format_db_row(row, row_body="Body text")
    assert rendered.startswith("# Real Title")
    # The title property itself should not appear twice.
    assert rendered.count("Real Title") == 1
    # Other props should still be listed.
    assert "Link" in rendered and "https://example.com" in rendered
    assert "Status" in rendered and "Open" in rendered


def test_process_notion_invalid_stub(tmp_path, monkeypatch):
    np_module = _patch_processor_pipeline(monkeypatch)

    bad = tmp_path / "bad.notion"
    bad.write_text(json.dumps({"kind": "notion_source"}))  # missing notion_id

    source_service = MagicMock()
    result = np_module.process_notion(
        project_id="p",
        source_id="s",
        source={"id": "s"},
        raw_file_path=bad,
        source_service=source_service,
    )
    assert not result["success"]
    source_service.update_source.assert_called()
