"""
Tests for DeepResearchAgent.

Covers:
- Bug 4 regression: output_path is required
- Smoke test with mocked Claude API
"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.ai_agents.deep_research_agent import DeepResearchAgent


@pytest.fixture
def agent():
    return DeepResearchAgent()


class TestOutputPathRequired:

    def test_raises_when_omitted(self, agent):
        """Calling research() without output_path raises ValueError."""
        with pytest.raises(ValueError, match="output_path is required"):
            agent.research(
                project_id="p1",
                source_id="s1",
                topic="AI",
                description="Research AI",
            )

    def test_raises_when_empty_string(self, agent):
        """Empty string output_path also raises ValueError."""
        with pytest.raises(ValueError, match="output_path is required"):
            agent.research(
                project_id="p1",
                source_id="s1",
                topic="AI",
                description="Research AI",
                output_path="",
            )

    @patch("app.services.ai_agents.deep_research_agent.message_service")
    @patch("app.services.ai_agents.deep_research_agent.claude_service")
    def test_works_with_output_path(self, mock_claude, mock_msg, agent):
        """Smoke test: valid output_path proceeds to Claude API call."""
        # Mock config loading
        agent._prompt_config = {
            "system_prompt": "You are a researcher.",
            "model": "test-model",
            "max_tokens": 100,
            "temperature": 0.5,
            "user_message_template": "Research: {topic}\n{description}\n{links_context}",
        }
        agent._tools = {
            "all_tools": [{"name": "write_research_to_file"}],
        }

        # Claude returns end_turn (no tool use) to exit the loop quickly
        mock_claude.send_message.return_value = {
            "content_blocks": [{"type": "text", "text": "Done"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

        result = agent.research(
            project_id="p1",
            source_id="s1",
            topic="AI",
            description="Research AI",
            output_path="/tmp/test_output.md",
        )

        # Should hit max iterations since no termination tool was called
        assert result["success"] is False
        assert "maximum iterations" in result["error"]
        mock_claude.send_message.assert_called()
