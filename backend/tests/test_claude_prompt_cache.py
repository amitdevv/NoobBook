"""
Tests for prompt-cache wiring in claude_service.

Covers:
- _system_block_with_cache: converts a plain string into the structured
  block form with cache_control attached.
- _tools_with_cache_breakpoint: marks only the LAST tool, never mutates
  the caller's list, and is a no-op for empty input.
- _messages_with_cache_breakpoint: marks only the last block of the LAST
  message, handles string / block-list / empty content shapes, never
  mutates the caller's list.
- ClaudeService._build_api_params: passes through unchanged when
  enable_prompt_cache=False; applies cache_control on system, tools, and
  the last message block when True. The Anthropic SDK rejects
  cache_control as a top-level kwarg — it's a per-block field — so these
  tests explicitly assert it is NOT set at the request top level.
"""
from app.services.integrations.claude.claude_service import (
    ClaudeService,
    _messages_with_cache_breakpoint,
    _system_block_with_cache,
    _tools_with_cache_breakpoint,
)


# ===========================================================================
# Helpers
# ===========================================================================

class TestSystemBlockWithCache:

    def test_wraps_string_in_block_with_ephemeral_cache(self):
        result = _system_block_with_cache("you are NoobBook")
        assert result == [
            {
                "type": "text",
                "text": "you are NoobBook",
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def test_returns_list_form(self):
        """The Anthropic API only honors cache_control on the block form."""
        result = _system_block_with_cache("x")
        assert isinstance(result, list)
        assert isinstance(result[0], dict)


class TestToolsWithCacheBreakpoint:

    def _tools(self):
        # Match the shape of tools loaded via tool_loader.load_tool().
        return [
            {"name": "search_sources", "description": "...", "input_schema": {}},
            {"name": "store_memory", "description": "...", "input_schema": {}},
        ]

    def test_marks_last_tool_only(self):
        result = _tools_with_cache_breakpoint(self._tools())
        assert "cache_control" not in result[0]
        assert result[-1]["cache_control"] == {"type": "ephemeral"}

    def test_does_not_mutate_caller_list(self):
        tools = self._tools()
        original_last = tools[-1].copy()
        _tools_with_cache_breakpoint(tools)
        # The caller's list and dicts must be untouched — chat builds a fresh
        # tool list per turn but tool defs themselves are module-level.
        assert "cache_control" not in tools[-1]
        assert tools[-1] == original_last

    def test_empty_list_is_noop(self):
        assert _tools_with_cache_breakpoint([]) == []

    def test_single_tool_marked(self):
        tools = [{"name": "only", "description": "", "input_schema": {}}]
        result = _tools_with_cache_breakpoint(tools)
        assert result[0]["cache_control"] == {"type": "ephemeral"}


class TestMessagesWithCacheBreakpoint:

    def test_string_content_converted_to_block_with_cache(self):
        result = _messages_with_cache_breakpoint([{"role": "user", "content": "hi"}])
        assert result == [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hi", "cache_control": {"type": "ephemeral"}}
                ],
            }
        ]

    def test_block_list_last_block_marked(self):
        result = _messages_with_cache_breakpoint([
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "a"},
                    {"type": "text", "text": "b"},
                ],
            }
        ])
        assert "cache_control" not in result[-1]["content"][0]
        assert result[-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}

    def test_only_last_message_marked(self):
        """In a multi-message list, earlier messages must remain untouched."""
        result = _messages_with_cache_breakpoint([
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "second"},
        ])
        assert result[0]["content"] == "first"
        assert result[1]["content"] == "reply"
        assert result[-1]["content"][0]["cache_control"] == {"type": "ephemeral"}

    def test_does_not_mutate_caller_list(self):
        msgs = [{"role": "user", "content": "hi"}]
        snapshot = {"role": "user", "content": "hi"}
        _messages_with_cache_breakpoint(msgs)
        assert msgs == [snapshot]

    def test_empty_list_is_noop(self):
        assert _messages_with_cache_breakpoint([]) == []

    def test_none_content_skipped_best_effort(self):
        msgs = [{"role": "user", "content": None}]
        assert _messages_with_cache_breakpoint(msgs) == msgs

    def test_empty_block_list_skipped(self):
        msgs = [{"role": "user", "content": []}]
        assert _messages_with_cache_breakpoint(msgs) == msgs


# ===========================================================================
# _build_api_params integration
# ===========================================================================

class TestBuildApiParamsCaching:

    def setup_method(self):
        self.svc = ClaudeService()

    def _build(self, **overrides):
        defaults = {
            "messages": [{"role": "user", "content": "hi"}],
            "system_prompt": "you are NoobBook",
            "model": "claude-sonnet-4-6",
            "max_tokens": 1024,
            "temperature": 0.0,
            "tools": [
                {"name": "a", "description": "", "input_schema": {}},
                {"name": "b", "description": "", "input_schema": {}},
            ],
            "tool_choice": None,
            "extra_headers": None,
        }
        defaults.update(overrides)
        return self.svc._build_api_params(**defaults)

    def test_caching_off_is_legacy_string_system(self):
        """Default (enable_prompt_cache=False) must keep the legacy contract."""
        params = self._build(enable_prompt_cache=False)
        assert params["system"] == "you are NoobBook"
        assert "cache_control" not in params["tools"][-1]
        # No cache_control on the messages array either — caching is off.
        assert params["messages"] == [{"role": "user", "content": "hi"}]
        # And critically: NOT at the request top level (SDK rejects it there).
        assert "cache_control" not in params

    def test_caching_on_never_sets_top_level_cache_control(self):
        """cache_control is a per-block field, not a request kwarg. Setting
        it at the top level triggers `TypeError: Messages.create() got an
        unexpected keyword argument 'cache_control'` on every released
        Anthropic SDK version. Regression guard."""
        params = self._build(enable_prompt_cache=True)
        assert "cache_control" not in params

    def test_caching_on_wraps_system(self):
        params = self._build(enable_prompt_cache=True)
        assert isinstance(params["system"], list)
        assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert params["system"][0]["text"] == "you are NoobBook"

    def test_caching_on_marks_last_tool(self):
        params = self._build(enable_prompt_cache=True)
        assert "cache_control" not in params["tools"][0]
        assert params["tools"][-1]["cache_control"] == {"type": "ephemeral"}

    def test_caching_on_marks_last_message_block(self):
        """Replaces the old (broken) top-level cache_control kwarg —
        the same caching effect is achieved by attaching cache_control
        to the last message's last content block."""
        params = self._build(enable_prompt_cache=True)
        last_block = params["messages"][-1]["content"][-1]
        assert last_block["cache_control"] == {"type": "ephemeral"}

    def test_caching_on_with_no_tools_does_not_crash(self):
        params = self._build(enable_prompt_cache=True, tools=None)
        # No tools key when tools is falsy, but system should still cache.
        assert "tools" not in params
        assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
        # Messages-array breakpoint is independent of tools.
        assert params["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
        assert "cache_control" not in params

    def test_caching_on_with_no_system_does_not_crash(self):
        params = self._build(enable_prompt_cache=True, system_prompt=None)
        assert "system" not in params
        assert params["tools"][-1]["cache_control"] == {"type": "ephemeral"}
        # Messages-array breakpoint is independent of system.
        assert params["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
        assert "cache_control" not in params
