"""
Database Analyzer Agent Executor - Executes analyze_database_agent tool calls from main chat.

Educational Note: This executor bridges main_chat_service and database_analyzer_agent.
"""

from typing import Any, Dict

from app.services.ai_agents.database_analyzer_agent import database_analyzer_agent


def execute(project_id: str, source_id: str, query: str) -> Dict[str, Any]:
    if not source_id:
        return {"success": False, "error": "source_id is required"}
    if not query:
        return {"success": False, "error": "query is required"}

    result = database_analyzer_agent.run(project_id=project_id, source_id=source_id, query=query)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Analysis failed")}

    content_parts = []
    summary = (result.get("summary") or "").strip()
    if summary:
        content_parts.append(summary)

    findings = result.get("findings") or []
    if findings:
        content_parts.append("Key findings:\n" + "\n".join([f"- {f}" for f in findings]))

    return {
        "success": True,
        "content": "\n\n".join([p for p in content_parts if p.strip()]) or "No analysis result",
        "sql_queries": result.get("sql_queries") or [],
        "iterations": result.get("iterations", 0),
        "usage": result.get("usage"),
    }

