"""Characterization tests for the analyzer agents' shared base.

These agents previously had no test coverage. The base extraction
(AnalyzerAgentBase: shared MAX_ITERATIONS + _save_execution) must be
behavior-preserving, so these tests lock in the inherited contract and one
full termination path through the CSV agent's loop.
"""
import os
from unittest.mock import patch

import pytest

# Importing the analyzer agents transitively pulls in supabase.auth_service,
# which builds a client at import time. Supply dummy creds (only if unset) so
# collection works in environments without a configured Supabase.
# JWT-shaped dummy keys: the supabase client validates key format at
# construction (3 dot-separated base64 segments). No network call is made here.
_FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiJ9.c2lnbmF0dXJl"
os.environ.setdefault("SUPABASE_URL", "http://localhost:8000")
os.environ.setdefault("SUPABASE_SERVICE_KEY", _FAKE_JWT)
os.environ.setdefault("SUPABASE_ANON_KEY", _FAKE_JWT)

from app.services.ai_agents.analyzer_agent_base import AnalyzerAgentBase
from app.services.ai_agents.csv_analyzer_agent import csv_analyzer_agent, CSVAnalyzerAgent
from app.services.ai_agents.database_analyzer_agent import database_analyzer_agent
from app.services.ai_agents.freshdesk_analyzer_agent import freshdesk_analyzer_agent
from app.services.ai_agents.mixpanel_analyzer_agent import mixpanel_analyzer_agent


ALL_AGENTS = [
    csv_analyzer_agent,
    database_analyzer_agent,
    freshdesk_analyzer_agent,
    mixpanel_analyzer_agent,
]


class TestSharedScaffolding:
    def test_all_agents_inherit_base(self):
        for agent in ALL_AGENTS:
            assert isinstance(agent, AnalyzerAgentBase)

    def test_iteration_ceiling_is_uniform(self):
        # Every analyzer must keep the codebase-wide 40-iteration ceiling.
        for agent in ALL_AGENTS:
            assert agent.MAX_ITERATIONS == 40

    def test_each_agent_keeps_distinct_identity(self):
        names = {a.AGENT_NAME for a in ALL_AGENTS}
        terminations = {a.TERMINATION_TOOL for a in ALL_AGENTS}
        assert len(names) == 4
        assert len(terminations) == 4

    def test_subclass_missing_identity_is_rejected(self):
        # A new analyzer that forgets AGENT_NAME / TERMINATION_TOOL should
        # fail loudly at definition time, not silently misbehave at runtime.
        with pytest.raises(TypeError):
            class _BadAgent(AnalyzerAgentBase):
                pass


class TestSharedSaveExecution:
    """The hoisted _save_execution must produce the same call each agent made before."""

    def _capture_save(self, agent, **kwargs):
        with patch(
            "app.services.ai_agents.analyzer_agent_base.agent_execution_service.save_agent_execution"
        ) as mock_save:
            agent._save_execution(
                project_id="p1",
                execution_id="e1",
                query="how many rows?",
                messages=[{"role": "user", "content": "x"}],
                result={"success": True},
                started_at="2026-01-01T00:00:00",
                source_id="s1",
            )
        mock_save.assert_called_once()
        return mock_save.call_args.kwargs

    def test_csv_save_uses_csv_prefix_and_name(self):
        kwargs = self._capture_save(csv_analyzer_agent)
        assert kwargs["agent_name"] == "csv_analyzer_agent"
        assert kwargs["task"] == "Analyze CSV: how many rows?"
        assert kwargs["metadata"] == {"source_id": "s1", "query": "how many rows?"}

    def test_database_save_uses_db_prefix_and_name(self):
        kwargs = self._capture_save(database_analyzer_agent)
        assert kwargs["agent_name"] == "database_analyzer_agent"
        assert kwargs["task"] == "Analyze DB: how many rows?"
        assert kwargs["metadata"] == {"source_id": "s1", "query": "how many rows?"}


class TestCsvLoopTermination:
    """Lock in the CSV agent's happy-path: a termination tool yields a success result."""

    def test_termination_returns_built_result(self):
        agent = CSVAnalyzerAgent()
        fake_response = {
            "usage": {"input_tokens": 7, "output_tokens": 11},
            "content_blocks": [{"type": "tool_use", "id": "t1", "name": "return_analysis", "input": {}}],
        }
        term_input = {"summary": "42 rows", "data": {"rows": 42}, "image_paths": []}

        with patch.object(agent, "_load_config", return_value={"user_message": "Analyze {filename} for {query}"}), \
             patch.object(agent, "_load_tools", return_value=[]), \
             patch("app.services.ai_agents.csv_analyzer_agent.claude_service.send_message", return_value=fake_response), \
             patch("app.services.ai_agents.csv_analyzer_agent.claude_parsing_utils.extract_tool_use_blocks",
                   return_value=[{"name": "return_analysis", "input": term_input, "id": "t1"}]), \
             patch("app.services.ai_agents.csv_analyzer_agent.claude_parsing_utils.serialize_content_blocks",
                   return_value=[]), \
             patch("app.services.ai_agents.csv_analyzer_agent.analysis_executor.execute_tool",
                   return_value=(dict(term_input), True)), \
             patch.object(agent, "_save_execution") as mock_save:
            result = agent.run("p1", "s1", "how many rows?")

        assert result["success"] is True
        assert result["summary"] == "42 rows"
        assert result["iterations"] == 1
        assert result["usage"] == {"input_tokens": 7, "output_tokens": 11}
        mock_save.assert_called_once()
