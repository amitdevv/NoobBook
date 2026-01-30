"""
Knowledge Base Integrations Package.

Educational Note: This package manages external knowledge base integrations
like Jira, Notion, GitHub, etc. The knowledge_base_service acts as the main
orchestrator that main_chat_service calls.

Structure:
- jira/jira_service.py - Jira API integration
- notion/notion_service.py - Notion API integration
- github_service.py - GitHub API integration (future)
- knowledge_base_service.py - Main orchestrator for all KB tools
"""
from app.services.integrations.knowledge_bases.jira import jira_service
from app.services.integrations.knowledge_bases.notion import notion_service
from app.services.integrations.knowledge_bases.knowledge_base_service import knowledge_base_service

__all__ = ["jira_service", "notion_service", "knowledge_base_service"]
