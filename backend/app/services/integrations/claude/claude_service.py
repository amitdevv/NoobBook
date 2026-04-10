"""
Claude Service - Wrapper for Claude API interactions.

Educational Note: This service provides a clean interface to the Claude API.
It's designed to be used by multiple callers (chat, subagents, tools, etc.)
with different configurations (prompts, tools, temperature).

Key Design Decisions:
- Stateless: Each call is independent, caller provides all context
- Flexible: Accepts variable parameters for different use cases
- Reusable: Can be called from main chat, subagents, RAG pipeline, etc.
"""
import logging
import os
from typing import Optional, List, Dict, Any, Callable
import anthropic

from app.utils.cost_tracking import add_usage as add_cost_usage

logger = logging.getLogger(__name__)


class ClaudeService:
    """
    Service class for Claude API interactions.

    Educational Note: This is a thin wrapper around the Anthropic client.
    It handles client initialization and provides a consistent interface
    for making API calls with various configurations.
    """

    def __init__(self):
        """Initialize the Claude service."""
        self._client: Optional[anthropic.Anthropic] = None
        self._opik_enabled: bool = False

    def _get_client(self) -> anthropic.Anthropic:
        """
        Get or create the Anthropic client.

        Educational Note: Lazy initialization to avoid errors if API key
        is not set at import time.

        Raises:
            ValueError: If ANTHROPIC_API_KEY is not set
        """
        if self._client is None:
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                logger.error("ANTHROPIC_API_KEY not found in environment")
                raise ValueError("ANTHROPIC_API_KEY not found in environment")

            client = anthropic.Anthropic(api_key=api_key)

            # Wrap with Opik observability if configured
            # Educational Note: track_anthropic() is a transparent wrapper that
            # auto-logs every API call (prompt, response, tokens, latency, cost)
            # to the Opik dashboard. If OPIK_API_KEY is not set, we skip entirely.
            opik_api_key = os.getenv('OPIK_API_KEY')
            if opik_api_key:
                try:
                    import opik
                    from opik.integrations.anthropic import track_anthropic

                    opik_url = os.getenv('OPIK_URL_OVERRIDE')
                    opik_workspace = os.getenv('OPIK_WORKSPACE')
                    opik_project = os.getenv('OPIK_PROJECT_NAME', 'NoobBook')

                    configure_kwargs = {"api_key": opik_api_key}
                    if opik_workspace:
                        configure_kwargs["workspace"] = opik_workspace
                    if opik_url:
                        configure_kwargs["url_override"] = opik_url

                    opik.configure(**configure_kwargs)
                    client = track_anthropic(client, project_name=opik_project)
                    self._opik_enabled = True
                    logger.info("Opik observability enabled (project: %s)", opik_project)
                except ImportError:
                    logger.warning("OPIK_API_KEY set but 'opik' package not installed. Skipping.")
                except Exception as e:
                    logger.warning("Failed to init Opik: %s. Continuing without observability.", e)

            self._client = client
        return self._client

    def _call_with_opik_context(
        self,
        api_fn,
        api_params: Dict[str, Any],
        *,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        """
        Call the Anthropic API, wrapping it in an Opik parent trace with metadata.

        Educational Note: track_anthropic() auto-creates a span for every
        client.messages.create() call, but the span is finalized before we can
        add metadata. By wrapping the call in @opik.track(), we create a parent
        trace. update_current_trace() injects user_id, project_id, and chat_id
        (as thread_id) into that parent. The track_anthropic span nests inside it.

        Falls back to a direct API call if Opik is not enabled.
        """
        if not self._opik_enabled:
            return api_fn(**api_params)

        try:
            import opik
            from opik.opik_context import update_current_trace

            @opik.track(name="noobbook_api_call")
            def tracked_call():
                # Inject metadata into the parent trace BEFORE the API call
                metadata = {}
                if project_id:
                    metadata["project_id"] = project_id
                if user_id:
                    metadata["user_id"] = user_id

                kwargs: Dict[str, Any] = {}
                if metadata:
                    kwargs["metadata"] = metadata
                if chat_id:
                    kwargs["thread_id"] = chat_id
                if tags:
                    kwargs["tags"] = tags

                if kwargs:
                    update_current_trace(**kwargs)

                return api_fn(**api_params)

            return tracked_call()
        except Exception:
            # If Opik wrapping fails, fall back to direct call
            return api_fn(**api_params)

    def _stream_with_opik_context(
        self,
        client,
        api_params: Dict[str, Any],
        on_text_delta: Optional[Callable[[str], None]],
        *,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        """Stream API call wrapped in Opik trace context, same pattern as _call_with_opik_context."""
        def _do_stream():
            with client.messages.stream(**api_params) as stream:
                for delta in stream.text_stream:
                    if on_text_delta:
                        on_text_delta(delta)
                return stream.get_final_message()

        if not self._opik_enabled:
            return _do_stream()

        try:
            import opik
            from opik.opik_context import update_current_trace

            @opik.track(name="noobbook_stream_call")
            def tracked_stream():
                metadata = {}
                if project_id:
                    metadata["project_id"] = project_id
                if user_id:
                    metadata["user_id"] = user_id
                kwargs: Dict[str, Any] = {}
                if metadata:
                    kwargs["metadata"] = metadata
                if chat_id:
                    kwargs["thread_id"] = chat_id
                if tags:
                    kwargs["tags"] = tags
                if kwargs:
                    update_current_trace(**kwargs)
                return _do_stream()

            return tracked_stream()
        except Exception:
            return _do_stream()

    def send_message(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send messages to Claude and get a response.

        Educational Note: This is the core method for Claude API interaction.
        Different callers can customize behavior via parameters:
        - Main chat: Just messages + system prompt
        - Subagents: Messages + tools + specific prompts
        - RAG: Messages with context + retrieval tools

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt for this conversation
            model: Claude model to use (default: claude-sonnet-4-6)
            max_tokens: Maximum tokens in response (default: 4096)
            temperature: Sampling temperature (default: 0.2)
            tools: Optional list of tool definitions for tool use
            tool_choice: Optional tool choice configuration
            extra_headers: Optional headers for beta features (e.g., {"anthropic-beta": "web-fetch-2025-09-10"})
            project_id: Optional project ID for cost tracking (if provided, costs are tracked)

        Returns:
            Dict containing:
                - content: The response content (text or tool_use blocks)
                - model: Model used
                - usage: Token usage stats
                - stop_reason: Why the response ended
                - raw_response: Full API response for advanced use cases

        Raises:
            ValueError: If API key is not configured
            anthropic.APIError: If API call fails
        """
        client = self._get_client()
        api_params = self._build_api_params(
            messages=messages,
            system_prompt=system_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            tool_choice=tool_choice,
            extra_headers=extra_headers,
        )

        # Make API call (wrapped in Opik trace with metadata if enabled)
        response = self._call_with_opik_context(
            client.messages.create, api_params,
            project_id=project_id, user_id=user_id, chat_id=chat_id, tags=tags,
        )

        # Track costs if project_id provided
        if project_id:
            add_cost_usage(
                project_id=project_id,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

        # Return raw response data - all parsing happens in claude_parsing_utils
        return {
            "content_blocks": response.content,  # Raw Anthropic content blocks
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "stop_reason": response.stop_reason,
        }

    def stream_message(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        project_id: Optional[str] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
        user_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Stream a Claude response and forward text deltas through a callback.

        Educational Note: This uses Anthropic's streaming API so callers can
        surface partial assistant text in real time while still receiving a
        final response object compatible with send_message().
        """
        client = self._get_client()
        api_params = self._build_api_params(
            messages=messages,
            system_prompt=system_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            tool_choice=tool_choice,
            extra_headers=extra_headers,
        )

        # Wrap streaming in Opik trace context for metadata attachment
        response = self._stream_with_opik_context(
            client, api_params, on_text_delta,
            project_id=project_id, user_id=user_id, chat_id=chat_id, tags=tags,
        )

        if project_id:
            add_cost_usage(
                project_id=project_id,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

        return {
            "content_blocks": response.content,
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "stop_reason": response.stop_reason,
        }

    def _build_api_params(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str],
        model: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[List[Dict[str, Any]]],
        tool_choice: Optional[Dict[str, Any]],
        extra_headers: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Build the shared Anthropic request payload."""
        # Build API call parameters
        api_params = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        # Add optional parameters only if provided
        if system_prompt:
            api_params["system"] = system_prompt

        if temperature != 0.2:  # Only set if not default
            api_params["temperature"] = temperature

        if tools:
            api_params["tools"] = tools

        if tool_choice:
            api_params["tool_choice"] = tool_choice

        # Add extra headers for beta features (e.g., web_fetch)
        if extra_headers:
            api_params["extra_headers"] = extra_headers

        return api_params

    def count_tokens(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """
        Count input tokens for a given set of messages without making an API call.

        Educational Note: This is useful for determining context size before:
        - Deciding whether to use RAG vs full context
        - Estimating costs
        - Checking if content fits within model limits

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt to include in count
            model: Claude model to use for tokenization
            tools: Optional list of tool definitions (tools also consume tokens)

        Returns:
            Number of input tokens
        """
        client = self._get_client()

        # Build API call parameters
        api_params = {
            "model": model,
            "messages": messages,
        }

        # Add optional parameters
        if system_prompt:
            api_params["system"] = system_prompt

        if tools:
            api_params["tools"] = tools

        # Call the count_tokens API
        response = client.messages.count_tokens(**api_params)

        return response.input_tokens


# Singleton instance for easy import
claude_service = ClaudeService()
