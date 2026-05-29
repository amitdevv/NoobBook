"""Agent execution logs — local-file debug records for agent runs.

These logs are intentionally NOT in Supabase: they're debugging artifacts
(full message chains, tool calls, results) written under
``data/projects/{project_id}/agents/{agent_name}/{execution_id}.json``.
Kept separate from message persistence since they're a distinct concern.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.utils.path_utils import get_web_agent_dir, get_agents_dir

logger = logging.getLogger(__name__)


class AgentExecutionService:
    """Read/write agent execution logs on the local filesystem."""

    def _get_agent_dir(self, project_id: str, agent_name: str) -> Path:
        """Return (creating if needed) an agent's execution-log directory."""
        if agent_name == "web_agent":
            return get_web_agent_dir(project_id)
        agents_dir = get_agents_dir(project_id)
        agent_dir = agents_dir / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)
        return agent_dir

    def save_agent_execution(
        self,
        project_id: str,
        agent_name: str,
        execution_id: str,
        task: str,
        messages: List[Dict[str, Any]],
        result: Dict[str, Any],
        started_at: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Write an execution log; return the execution_id, or None on failure."""
        if not project_id:
            return None

        try:
            agent_dir = self._get_agent_dir(project_id, agent_name)

            execution_log = {
                "execution_id": execution_id,
                "agent_name": agent_name,
                "task": task,
                "messages": messages,
                "result": result,
                "started_at": started_at,
                "completed_at": datetime.now().isoformat(),
            }
            if metadata:
                execution_log.update(metadata)

            log_file = agent_dir / f"{execution_id}.json"
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(execution_log, f, indent=2, ensure_ascii=False)

            return execution_id

        except Exception as e:
            logger.error("Failed to save %s execution log: %s", agent_name, e)
            return None

    def get_agent_execution(
        self,
        project_id: str,
        agent_name: str,
        execution_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Load a single execution log, or None if missing/unreadable."""
        try:
            log_file = self._get_agent_dir(project_id, agent_name) / f"{execution_id}.json"
            if not log_file.exists():
                return None
            with open(log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Failed to read %s execution log: %s", agent_name, e)
            return None

    def list_agent_executions(
        self,
        project_id: str,
        agent_name: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List execution summaries (no message chains), newest first."""
        try:
            agent_dir = self._get_agent_dir(project_id, agent_name)
            if not agent_dir.exists():
                return []

            executions = []
            for log_file in agent_dir.glob("*.json"):
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        log = json.load(f)
                        executions.append({
                            "execution_id": log.get("execution_id"),
                            "task": log.get("task", "")[:100],
                            "completed_at": log.get("completed_at"),
                            "success": log.get("result", {}).get("success", False),
                        })
                except (json.JSONDecodeError, IOError):
                    continue

            executions.sort(key=lambda x: x.get("completed_at", ""), reverse=True)
            return executions[:limit]

        except Exception as e:
            logger.error("Failed to list %s executions: %s", agent_name, e)
            return []


# Singleton instance for easy import
agent_execution_service = AgentExecutionService()
