"""
Freshdesk Analyzer Agent - Agentic loop for analyzing Freshdesk ticket data.

Educational Note: Follows the same pattern as database_analyzer_agent.py.
Claude iterates with tools (schema_info, query_runner) until it calls
return_ticket_analysis to terminate with structured output.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.config import prompt_loader, tool_loader
from app.services.integrations.claude import claude_service
from app.utils import claude_parsing_utils
from app.services.tool_executors.freshdesk_executor import freshdesk_executor

logger = logging.getLogger(__name__)


class FreshdeskAnalyzerAgent:
    AGENT_NAME = "freshdesk_analyzer_agent"
    MAX_ITERATIONS = 15
    TERMINATION_TOOL = "return_ticket_analysis"

    def __init__(self):
        self._tools = None

    def _load_tools(self) -> List[Dict[str, Any]]:
        if self._tools is None:
            self._tools = tool_loader.load_tools_from_category("freshdesk_agent")
        return self._tools

    def run(self, project_id: str, source_id: str, query: str, chat_id: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Run the Freshdesk analysis agentic loop.
        Always closes the DB connection on exit to prevent leaks."""
        execution_id = str(uuid.uuid4())[:8]
        logger.info("[FreshdeskAgent:%s] Starting analysis for source %s", execution_id, source_id)

        # Pre-flight: verify DB connection
        if not freshdesk_executor.validate_connection():
            return {"success": False, "error": "Cannot connect to database"}

        # Load config
        prompt_config = prompt_loader.get_prompt_config(self.AGENT_NAME)
        tools = self._load_tools()

        system_prompt = prompt_config.get("system_prompt", "")
        model = prompt_config.get("model", "claude-sonnet-4-6")
        max_tokens = prompt_config.get("max_tokens", 4096)
        temperature = prompt_config.get("temperature", 0.0)

        messages = [{"role": "user", "content": f"Freshdesk source ID: {source_id}\n\nUser question: {query}"}]

        total_usage = {"input_tokens": 0, "output_tokens": 0}
        all_queries: List[str] = []
        consecutive_errors = 0

        try:
            for iteration in range(1, self.MAX_ITERATIONS + 1):
                logger.info("[FreshdeskAgent:%s] Iteration %d", execution_id, iteration)

                response = claude_service.send_message(
                    messages=messages,
                    system_prompt=system_prompt,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=tools,
                    project_id=project_id,
                    tags=["query"],
                    chat_id=chat_id,
                    user_id=user_id,
                )

                # Track usage
                usage = response.get("usage", {})
                total_usage["input_tokens"] += usage.get("input_tokens", 0)
                total_usage["output_tokens"] += usage.get("output_tokens", 0)

                if claude_parsing_utils.is_end_turn(response):
                    text = claude_parsing_utils.extract_text(response)
                    return {
                        "success": True,
                        "content": text,
                        "summary": text,
                        "findings": [],
                        "recommendations": [],
                        "sql_queries": all_queries,
                        "iterations": iteration,
                        "usage": total_usage,
                    }

                if not claude_parsing_utils.is_tool_use(response):
                    text = claude_parsing_utils.extract_text(response)
                    return {"success": True, "content": text, "iterations": iteration, "usage": total_usage}

                # Process tool calls
                tool_blocks = claude_parsing_utils.extract_tool_use_blocks(response)
                content_blocks = response.get("content_blocks", [])
                messages.append({"role": "assistant", "content": content_blocks})

                tool_results = []
                terminated = False
                termination_result = None

                for block in tool_blocks:
                    tool_name = block.get("name", "")
                    tool_input = block.get("input", {})
                    tool_id = block.get("id", "")

                    result, is_term = freshdesk_executor.execute_tool(
                        tool_name, tool_input, project_id, source_id,
                    )

                    if tool_name == "query_runner" and tool_input.get("sql_query"):
                        all_queries.append(tool_input["sql_query"])

                    if not result.get("success", True) if isinstance(result, dict) else False:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0

                    if consecutive_errors >= 3:
                        return {"success": False, "error": "Too many consecutive tool errors", "sql_queries": all_queries}

                    if is_term:
                        terminated = True
                        termination_result = result

                    import json
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps(result) if isinstance(result, dict) else str(result),
                    })

                messages.append({"role": "user", "content": tool_results})

                if terminated and termination_result:
                    return {
                        "success": True,
                        "content": termination_result.get("summary", ""),
                        "summary": termination_result.get("summary", ""),
                        "findings": termination_result.get("findings", []),
                        "recommendations": termination_result.get("recommendations", []),
                        "sql_queries": all_queries,
                        "iterations": iteration,
                        "usage": total_usage,
                    }

            # Max iterations reached
            return {"success": False, "error": f"Max iterations ({self.MAX_ITERATIONS}) reached", "sql_queries": all_queries}
        finally:
            freshdesk_executor.close()


freshdesk_analyzer_agent = FreshdeskAnalyzerAgent()
