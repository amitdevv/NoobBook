"""
Tests for WebsiteToolExecutor.

Covers:
- _get_content_type mapping
- Bug 3 regression: upload failure returns error string to agent
"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.tool_executors.website_tool_executor import WebsiteToolExecutor


@pytest.fixture
def executor():
    return WebsiteToolExecutor()


# ===========================================================================
# Content type detection
# ===========================================================================

class TestGetContentType:

    def test_css(self, executor):
        assert executor._get_content_type("style.css") == "text/css; charset=utf-8"

    def test_js(self, executor):
        assert executor._get_content_type("app.js") == "application/javascript; charset=utf-8"

    def test_html(self, executor):
        assert executor._get_content_type("index.html") == "text/html; charset=utf-8"

    def test_unknown_defaults_to_html(self, executor):
        assert executor._get_content_type("readme.txt") == "text/html; charset=utf-8"


# ===========================================================================
# Bug 3: upload failure returns error to agent
# ===========================================================================

class TestUploadFailureHandling:
    """upload_studio_file returning None should produce an error message."""

    @patch("app.services.tool_executors.website_tool_executor.studio_index_service")
    @patch("app.services.tool_executors.website_tool_executor.storage_service")
    def test_create_file_error_on_upload_failure(
        self, mock_storage, mock_studio, executor
    ):
        mock_storage.upload_studio_file.return_value = None
        mock_studio.get_website_job.return_value = {"images": []}

        result, is_term = executor.execute_tool(
            "create_file",
            {"filename": "index.html", "content": "<h1>Hi</h1>"},
            {
                "project_id": "p1",
                "job_id": "j1",
                "created_files": [],
                "generated_images": [],
            },
        )

        assert "Error" in result["message"]
        assert "upload" in result["message"].lower() or "storage" in result["message"].lower()

    @patch("app.services.tool_executors.website_tool_executor.studio_index_service")
    @patch("app.services.tool_executors.website_tool_executor.storage_service")
    def test_update_file_lines_error_on_upload_failure(
        self, mock_storage, mock_studio, executor
    ):
        mock_storage.download_studio_file.return_value = "line1\nline2\nline3\n"
        mock_storage.upload_studio_file.return_value = None
        mock_studio.get_website_job.return_value = {"images": []}

        result, is_term = executor.execute_tool(
            "update_file_lines",
            {"filename": "index.html", "start_line": 1, "end_line": 1, "new_content": "replaced"},
            {"project_id": "p1", "job_id": "j1", "created_files": [], "generated_images": []},
        )

        assert "Error" in result["message"]

    @patch("app.services.tool_executors.website_tool_executor.studio_index_service")
    @patch("app.services.tool_executors.website_tool_executor.storage_service")
    def test_insert_code_error_on_upload_failure(
        self, mock_storage, mock_studio, executor
    ):
        mock_storage.download_studio_file.return_value = "line1\nline2\n"
        mock_storage.upload_studio_file.return_value = None
        mock_studio.get_website_job.return_value = {"images": []}

        result, is_term = executor.execute_tool(
            "insert_code",
            {"filename": "index.html", "after_line": 1, "content": "inserted"},
            {"project_id": "p1", "job_id": "j1", "created_files": [], "generated_images": []},
        )

        assert "Error" in result["message"]
