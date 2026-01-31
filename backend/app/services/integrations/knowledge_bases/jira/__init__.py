"""
Jira Integration Package.

Educational Note: This package provides Jira API integration for querying
projects, issues, and other Jira data from the chat interface.
"""
from app.services.integrations.knowledge_bases.jira.jira_service import jira_service

__all__ = ["jira_service"]
