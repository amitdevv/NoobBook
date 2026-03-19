"""
Freshdesk Analyzer Agent Executor - Bridge between main_chat_service and the agent.

Educational Note: Follows database_analyzer_agent_executor.py pattern.
Formats the agent result for display in the chat response.
"""

import logging
from typing import Any, Dict

from app.services.ai_agents.freshdesk_analyzer_agent import freshdesk_analyzer_agent

logger = logging.getLogger(__name__)


def execute(project_id: str, source_id: str, query: str) -> Dict[str, Any]:
    """Execute Freshdesk analysis and format result for chat."""
    try:
        result = freshdesk_analyzer_agent.run(
            project_id=project_id,
            source_id=source_id,
            query=query,
        )

        if not result.get("success"):
            return {"success": False, "error": result.get("error", "Analysis failed")}

        # Build formatted content for chat display
        parts = []

        summary = result.get("summary") or result.get("content", "")
        if summary:
            parts.append(summary)

        findings = result.get("findings", [])
        if findings:
            parts.append("\n**Key Findings:**")
            for f in findings:
                parts.append(f"- {f}")

        recommendations = result.get("recommendations", [])
        if recommendations:
            parts.append("\n**Recommendations:**")
            for r in recommendations:
                parts.append(f"- {r}")

        content = "\n".join(parts) if parts else "Analysis complete but no results generated."

        return {
            "success": True,
            "content": content,
            "sql_queries": result.get("sql_queries", []),
            "iterations": result.get("iterations", 0),
            "usage": result.get("usage", {}),
        }

    except Exception as e:
        logger.exception("Freshdesk analysis failed for source %s", source_id)
        return {"success": False, "error": str(e)}
