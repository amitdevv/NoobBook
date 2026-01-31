"""
Notion Integration Package.

Educational Note: This package provides Notion API integration for querying
pages and databases from the chat interface.
"""
from app.services.integrations.knowledge_bases.notion.notion_service import notion_service

__all__ = ["notion_service"]
