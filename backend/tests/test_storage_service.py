"""
Tests for Supabase storage_service.

Covers:
- Bug 1 regression: delete_user_brand_assets folder detection (id=None → folder)
- Bug 2 regression: .list() calls pass limit > 100
- Recursive delete and list operations
- Chunk listing and parsing
"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.integrations.supabase import storage_service
from app.services.integrations.supabase.storage_service import _LIST_OPTIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _file_entry(name: str, file_id: str = "some-uuid") -> dict:
    """Simulate a Supabase Storage file entry (has an id)."""
    return {"name": name, "id": file_id}


def _folder_entry(name: str) -> dict:
    """Simulate a Supabase Storage folder entry (id is None)."""
    return {"name": name, "id": None}


# ===========================================================================
# Bug 1: delete_user_brand_assets — folder detection
# ===========================================================================

class TestDeleteUserBrandAssets:
    """Regression tests for inverted folder detection (Bug 1)."""

    def test_recurses_into_folders(self, patch_storage_client):
        """Folders (id=None) should be recursed, files (id=uuid) deleted."""
        _, mock_bucket = patch_storage_client

        # Root lists one folder "asset1" and one loose file
        # Then asset1/ lists two files
        mock_bucket.list.side_effect = [
            [_folder_entry("asset1"), _file_entry("loose.png")],
            [_file_entry("logo.svg"), _file_entry("icon.png")],
        ]

        result = storage_service.delete_user_brand_assets("user-1")

        assert result is True
        mock_bucket.remove.assert_called_once()
        removed = mock_bucket.remove.call_args[0][0]
        assert "user-1/brand/loose.png" in removed
        assert "user-1/brand/asset1/logo.svg" in removed
        assert "user-1/brand/asset1/icon.png" in removed
        assert len(removed) == 3

    def test_nested_folders(self, patch_storage_client):
        """Two levels of nested folders are handled correctly."""
        _, mock_bucket = patch_storage_client

        # Root → folder "a"
        # a/ → folder "b" + file "x.png"
        # b/ → file "y.png"
        mock_bucket.list.side_effect = [
            [_folder_entry("a")],
            [_folder_entry("b"), _file_entry("x.png")],
            [_file_entry("y.png")],
        ]

        result = storage_service.delete_user_brand_assets("user-2")

        assert result is True
        removed = mock_bucket.remove.call_args[0][0]
        assert "user-2/brand/a/x.png" in removed
        assert "user-2/brand/a/b/y.png" in removed
        assert len(removed) == 2

    def test_empty_brand_folder(self, patch_storage_client):
        """Empty brand folder returns True without calling remove."""
        _, mock_bucket = patch_storage_client
        mock_bucket.list.return_value = []

        result = storage_service.delete_user_brand_assets("user-3")

        assert result is True
        mock_bucket.remove.assert_not_called()

    def test_only_files_no_folders(self, patch_storage_client):
        """Flat structure with only files — all deleted."""
        _, mock_bucket = patch_storage_client
        mock_bucket.list.return_value = [
            _file_entry("a.png"),
            _file_entry("b.jpg"),
        ]

        result = storage_service.delete_user_brand_assets("user-4")

        assert result is True
        removed = mock_bucket.remove.call_args[0][0]
        assert len(removed) == 2


# ===========================================================================
# Bug 2: .list() calls pass limit option
# ===========================================================================

class TestListLimitOptions:
    """Ensure all .list() calls pass a high limit to avoid silent truncation."""

    def test_list_source_chunks_passes_limit(self, patch_storage_client):
        _, mock_bucket = patch_storage_client
        mock_bucket.list.return_value = []

        storage_service.list_source_chunks("proj-1", "src-1")

        mock_bucket.list.assert_called_once()
        call_args = mock_bucket.list.call_args
        assert call_args[1].get("options") == _LIST_OPTIONS or \
            (len(call_args[0]) > 1 and call_args[0][1] == _LIST_OPTIONS) or \
            call_args.kwargs.get("options") == _LIST_OPTIONS

    def test_delete_source_chunks_passes_limit(self, patch_storage_client):
        _, mock_bucket = patch_storage_client
        mock_bucket.list.return_value = []

        storage_service.delete_source_chunks("proj-1", "src-1")

        mock_bucket.list.assert_called_once()
        _, kwargs = mock_bucket.list.call_args
        assert kwargs.get("options") == _LIST_OPTIONS

    def test_delete_studio_job_files_passes_limit(self, patch_storage_client):
        _, mock_bucket = patch_storage_client
        mock_bucket.list.return_value = [_file_entry("file.md")]

        storage_service.delete_studio_job_files("proj-1", "prds", "job-1")

        _, kwargs = mock_bucket.list.call_args
        assert kwargs.get("options") == _LIST_OPTIONS

    def test_list_studio_job_files_passes_limit(self, patch_storage_client):
        _, mock_bucket = patch_storage_client
        mock_bucket.list.return_value = [_file_entry("file.md")]

        storage_service.list_studio_job_files("proj-1", "prds", "job-1")

        _, kwargs = mock_bucket.list.call_args
        assert kwargs.get("options") == _LIST_OPTIONS


# ===========================================================================
# Recursive delete / list for studio jobs
# ===========================================================================

class TestDeleteStudioJobFiles:

    def test_recurses_subfolders(self, patch_storage_client):
        """delete_studio_job_files recurses into subfolders."""
        _, mock_bucket = patch_storage_client

        mock_bucket.list.side_effect = [
            [_folder_entry("assets"), _file_entry("index.html")],
            [_file_entry("style.css")],
        ]

        result = storage_service.delete_studio_job_files("p1", "websites", "j1")

        assert result is True
        removed = mock_bucket.remove.call_args[0][0]
        assert "p1/websites/j1/index.html" in removed
        assert "p1/websites/j1/assets/style.css" in removed

    def test_deeply_nested(self, patch_storage_client):
        """Three levels deep: root → assets/ → images/ → pic.png"""
        _, mock_bucket = patch_storage_client

        mock_bucket.list.side_effect = [
            [_folder_entry("assets")],
            [_folder_entry("images")],
            [_file_entry("pic.png")],
        ]

        result = storage_service.delete_studio_job_files("p1", "websites", "j1")

        assert result is True
        removed = mock_bucket.remove.call_args[0][0]
        assert "p1/websites/j1/assets/images/pic.png" in removed
        assert len(removed) == 1


class TestListStudioJobFiles:

    def test_returns_relative_paths(self, patch_storage_client):
        """File names are relative to the job root."""
        _, mock_bucket = patch_storage_client

        mock_bucket.list.side_effect = [
            [_folder_entry("assets"), _file_entry("index.html")],
            [_file_entry("style.css")],
        ]

        files = storage_service.list_studio_job_files("p1", "websites", "j1")

        names = [f["name"] for f in files]
        assert "index.html" in names
        assert "assets/style.css" in names


# ===========================================================================
# Chunk listing and download
# ===========================================================================

class TestListSourceChunks:

    def test_parses_correctly(self, patch_storage_client):
        """Chunks are downloaded, parsed for page number, and returned."""
        _, mock_bucket = patch_storage_client

        mock_bucket.list.return_value = [
            {"name": "src1_page_3_chunk_1.txt"},
            {"name": "src1_page_3_chunk_2.txt"},
        ]
        mock_bucket.download.side_effect = [
            b"chunk one text",
            b"chunk two text",
        ]

        chunks = storage_service.list_source_chunks("proj-1", "src1")

        assert len(chunks) == 2
        assert chunks[0]["page_number"] == 3
        assert chunks[0]["text"] == "chunk one text"
        assert chunks[0]["source_id"] == "src1"

    def test_handles_download_failure(self, patch_storage_client):
        """If one chunk download fails, the rest are still returned."""
        _, mock_bucket = patch_storage_client

        mock_bucket.list.return_value = [
            {"name": "src1_page_1_chunk_1.txt"},
            {"name": "src1_page_1_chunk_2.txt"},
        ]
        mock_bucket.download.side_effect = [
            Exception("network error"),
            b"chunk two text",
        ]

        chunks = storage_service.list_source_chunks("proj-1", "src1")

        assert len(chunks) == 1
        assert chunks[0]["chunk_id"] == "src1_page_1_chunk_2"
