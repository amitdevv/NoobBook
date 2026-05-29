"""Shared scaffolding for the single-source analyzer agents.

The CSV, database, Freshdesk, and Mixpanel analyzers each run their own agentic
loop. The loop *bodies* are deliberately NOT shared: they diverge in essential
ways (per-tool progress events, pre-flight connection checks, termination
timing, result shape, synthesis fallback), and a one-size template would trade
readable self-contained loops for a tangle of override hooks.

What every analyzer genuinely shares lives here — the iteration ceiling and the
debug-log save. A new analyzer subclasses this, sets ``AGENT_NAME`` /
``TERMINATION_TOOL`` / ``EXECUTION_TASK_PREFIX``, and writes its own ``run()``.
"""
from typing import Any, Dict, List

from app.services.data_services import agent_execution_service


class AnalyzerAgentBase:
    """Common constants + execution logging for analyzer agents."""

    # Iteration ceiling shared with every other agent in the codebase. Most
    # analyses finish in far fewer rounds; the cap only bounds worst-case spend.
    MAX_ITERATIONS = 40

    # Subclasses override these.
    AGENT_NAME: str = ""
    TERMINATION_TOOL: str = ""
    # Prefix for the saved execution-log task line, e.g. "Analyze CSV".
    EXECUTION_TASK_PREFIX: str = "Analyze"

    def __init_subclass__(cls, **kwargs: object) -> None:
        # Fail loudly at import time if a new analyzer forgets its identity:
        # an empty AGENT_NAME writes logs to a malformed path, and an empty
        # TERMINATION_TOOL means the loop never terminates early.
        super().__init_subclass__(**kwargs)
        missing = [a for a in ("AGENT_NAME", "TERMINATION_TOOL") if not getattr(cls, a, "")]
        if missing:
            raise TypeError(
                f"{cls.__name__} must set non-empty {', '.join(missing)}"
            )

    def _save_execution(
        self,
        project_id: str,
        execution_id: str,
        query: str,
        messages: List[Dict[str, Any]],
        result: Dict[str, Any],
        started_at: str,
        source_id: str,
    ) -> None:
        """Persist a local debug execution log for this agent run."""
        agent_execution_service.save_agent_execution(
            project_id=project_id,
            agent_name=self.AGENT_NAME,
            execution_id=execution_id,
            task=f"{self.EXECUTION_TASK_PREFIX}: {query}",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "query": query},
        )
