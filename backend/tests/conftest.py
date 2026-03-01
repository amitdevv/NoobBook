"""
Shared pytest fixtures for NoobBook backend tests.
"""
import pytest
from unittest.mock import MagicMock, patch

from app import create_app


@pytest.fixture
def app():
    """Create a Flask test application."""
    app = create_app("testing")
    yield app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def mock_supabase():
    """
    Returns a (mock_client, mock_bucket) pair.

    mock_client.storage.from_(bucket_name) always returns mock_bucket,
    so tests can set mock_bucket.list.return_value etc.
    """
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.storage.from_.return_value = mock_bucket
    return mock_client, mock_bucket


@pytest.fixture
def patch_storage_client(mock_supabase):
    """
    Patch _get_client() and is_supabase_enabled() so storage functions
    use the mock instead of a real Supabase connection.
    """
    mock_client, mock_bucket = mock_supabase
    with patch(
        "app.services.integrations.supabase.storage_service._get_client",
        return_value=mock_client,
    ), patch(
        "app.services.integrations.supabase.storage_service.is_supabase_enabled",
        return_value=True,
    ):
        yield mock_client, mock_bucket
