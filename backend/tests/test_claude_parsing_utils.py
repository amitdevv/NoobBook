"""
Tests for claude_parsing_utils.

Covers:
- Response type checks (is_end_turn, is_tool_use, get_stop_reason)
- Text extraction from dict and SDK-object formats
- Tool use block extraction and filtering
- Tool result building (is_error handling, non-string conversion)
- Serialization of Anthropic SDK objects
- Token usage extraction
"""
import pytest
from types import SimpleNamespace

from app.utils.claude_parsing_utils import (
    is_end_turn,
    is_tool_use,
    get_stop_reason,
    extract_text,
    extract_citations,
    extract_tool_use_blocks,
    extract_tool_inputs,
    extract_server_tool_use_blocks,
    extract_server_tool_results,
    has_server_tool_use,
    build_tool_result_content,
    build_single_tool_result,
    serialize_content_blocks,
    _serialize_anthropic_object,
    get_token_usage,
    get_model,
)


# ---------------------------------------------------------------------------
# Helpers — simulate Anthropic SDK objects via SimpleNamespace
# ---------------------------------------------------------------------------

def _sdk_text(text: str, citations=None):
    """Simulate an Anthropic TextBlock object."""
    obj = SimpleNamespace(type="text", text=text)
    if citations is not None:
        obj.citations = citations
    return obj


def _sdk_tool_use(tool_id: str, name: str, input_data: dict):
    """Simulate an Anthropic ToolUseBlock object."""
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=input_data)


def _sdk_server_tool_use(tool_id: str, name: str, input_data: dict):
    return SimpleNamespace(type="server_tool_use", id=tool_id, name=name, input=input_data)


def _sdk_server_result(result_type: str, tool_use_id: str, content):
    return SimpleNamespace(type=result_type, tool_use_id=tool_use_id, content=content)


def _dict_text(text: str, citations=None):
    block = {"type": "text", "text": text}
    if citations is not None:
        block["citations"] = citations
    return block


def _dict_tool_use(tool_id: str, name: str, input_data: dict):
    return {"type": "tool_use", "id": tool_id, "name": name, "input": input_data}


# ===========================================================================
# Response type checks
# ===========================================================================

class TestResponseTypeChecks:

    def test_is_end_turn_true(self):
        assert is_end_turn({"stop_reason": "end_turn"}) is True

    def test_is_end_turn_false_for_tool_use(self):
        assert is_end_turn({"stop_reason": "tool_use"}) is False

    def test_is_end_turn_false_for_missing(self):
        assert is_end_turn({}) is False

    def test_is_tool_use_true(self):
        assert is_tool_use({"stop_reason": "tool_use"}) is True

    def test_is_tool_use_false_for_end_turn(self):
        assert is_tool_use({"stop_reason": "end_turn"}) is False

    def test_get_stop_reason(self):
        assert get_stop_reason({"stop_reason": "max_tokens"}) == "max_tokens"

    def test_get_stop_reason_missing(self):
        assert get_stop_reason({}) == ""


# ===========================================================================
# Text extraction
# ===========================================================================

class TestExtractText:

    def test_dict_format(self):
        resp = {"content_blocks": [_dict_text("hello")]}
        assert extract_text(resp) == "hello"

    def test_sdk_format(self):
        resp = {"content_blocks": [_sdk_text("world")]}
        assert extract_text(resp) == "world"

    def test_mixed_blocks_only_text(self):
        """Text extraction ignores tool_use blocks."""
        resp = {
            "content_blocks": [
                _dict_text("I'll search"),
                _dict_tool_use("t1", "search", {"q": "x"}),
                _dict_text("Found it"),
            ]
        }
        assert extract_text(resp) == "I'll search\nFound it"

    def test_empty_content_blocks(self):
        assert extract_text({"content_blocks": []}) == ""

    def test_missing_content_blocks(self):
        assert extract_text({}) == ""

    def test_multiple_text_blocks_joined(self):
        resp = {"content_blocks": [_sdk_text("a"), _sdk_text("b"), _sdk_text("c")]}
        assert extract_text(resp) == "a\nb\nc"


# ===========================================================================
# Citation extraction
# ===========================================================================

class TestExtractCitations:

    def test_dict_citations(self):
        cit = [{"url": "https://x.com", "title": "X", "cited_text": "stuff"}]
        resp = {"content_blocks": [_dict_text("text", citations=cit)]}
        result = extract_citations(resp)
        assert len(result) == 1
        assert result[0]["url"] == "https://x.com"

    def test_sdk_citations(self):
        cit_obj = SimpleNamespace(url="https://y.com", title="Y", cited_text="more")
        resp = {"content_blocks": [_sdk_text("text", citations=[cit_obj])]}
        result = extract_citations(resp)
        assert len(result) == 1
        assert result[0]["title"] == "Y"

    def test_no_citations(self):
        resp = {"content_blocks": [_dict_text("plain text")]}
        assert extract_citations(resp) == []


# ===========================================================================
# Tool use block extraction
# ===========================================================================

class TestExtractToolUseBlocks:

    def test_dict_format(self):
        resp = {
            "content_blocks": [
                _dict_tool_use("t1", "search", {"q": "test"}),
            ]
        }
        blocks = extract_tool_use_blocks(resp)
        assert len(blocks) == 1
        assert blocks[0]["id"] == "t1"
        assert blocks[0]["name"] == "search"
        assert blocks[0]["input"] == {"q": "test"}

    def test_sdk_format(self):
        resp = {
            "content_blocks": [
                _sdk_tool_use("t2", "memory", {"data": "x"}),
            ]
        }
        blocks = extract_tool_use_blocks(resp)
        assert len(blocks) == 1
        assert blocks[0]["name"] == "memory"

    def test_filter_by_name(self):
        resp = {
            "content_blocks": [
                _dict_tool_use("t1", "search", {}),
                _dict_tool_use("t2", "memory", {}),
                _dict_tool_use("t3", "search", {}),
            ]
        }
        blocks = extract_tool_use_blocks(resp, tool_name="search")
        assert len(blocks) == 2
        assert all(b["name"] == "search" for b in blocks)

    def test_no_match(self):
        resp = {"content_blocks": [_dict_text("hello")]}
        assert extract_tool_use_blocks(resp) == []

    def test_extract_tool_inputs(self):
        resp = {
            "content_blocks": [
                _dict_tool_use("t1", "search", {"q": "alpha"}),
                _dict_tool_use("t2", "search", {"q": "beta"}),
            ]
        }
        inputs = extract_tool_inputs(resp, "search")
        assert inputs == [{"q": "alpha"}, {"q": "beta"}]


# ===========================================================================
# Server tool extraction
# ===========================================================================

class TestServerToolExtraction:

    def test_extract_server_tool_use_sdk(self):
        resp = {
            "content_blocks": [
                _sdk_server_tool_use("s1", "web_search", {"query": "AI"}),
            ]
        }
        blocks = extract_server_tool_use_blocks(resp)
        assert len(blocks) == 1
        assert blocks[0]["name"] == "web_search"

    def test_extract_server_tool_use_dict(self):
        resp = {
            "content_blocks": [
                {"type": "server_tool_use", "id": "s1", "name": "web_fetch", "input": {}},
            ]
        }
        blocks = extract_server_tool_use_blocks(resp, tool_name="web_fetch")
        assert len(blocks) == 1

    def test_has_server_tool_use(self):
        resp = {"content_blocks": [_sdk_server_tool_use("s1", "web_search", {})]}
        assert has_server_tool_use(resp) is True

    def test_has_no_server_tool_use(self):
        resp = {"content_blocks": [_dict_text("no tools")]}
        assert has_server_tool_use(resp) is False

    def test_extract_server_tool_results_dict(self):
        resp = {
            "content_blocks": [
                {"type": "web_search_tool_result", "tool_use_id": "s1", "content": "results"},
            ]
        }
        results = extract_server_tool_results(resp)
        assert len(results) == 1
        assert results[0]["type"] == "web_search_tool_result"

    def test_extract_server_tool_results_filter(self):
        resp = {
            "content_blocks": [
                {"type": "web_search_tool_result", "tool_use_id": "s1", "content": "a"},
                {"type": "web_fetch_tool_result", "tool_use_id": "s2", "content": "b"},
            ]
        }
        results = extract_server_tool_results(resp, result_type="web_fetch_tool_result")
        assert len(results) == 1
        assert results[0]["tool_use_id"] == "s2"


# ===========================================================================
# Tool result building
# ===========================================================================

class TestBuildToolResult:

    def test_basic_result(self):
        results = build_tool_result_content([
            {"tool_use_id": "t1", "result": "68°F sunny"},
        ])
        assert len(results) == 1
        assert results[0]["type"] == "tool_result"
        assert results[0]["tool_use_id"] == "t1"
        assert results[0]["content"] == "68°F sunny"
        assert "is_error" not in results[0]

    def test_error_result(self):
        results = build_tool_result_content([
            {"tool_use_id": "t1", "result": "timeout", "is_error": True},
        ])
        assert results[0]["is_error"] is True

    def test_non_error_omits_key(self):
        results = build_tool_result_content([
            {"tool_use_id": "t1", "result": "ok", "is_error": False},
        ])
        assert "is_error" not in results[0]

    def test_non_string_result_converted(self):
        results = build_tool_result_content([
            {"tool_use_id": "t1", "result": {"data": 42}},
        ])
        assert isinstance(results[0]["content"], str)
        assert "42" in results[0]["content"]

    def test_multiple_results(self):
        results = build_tool_result_content([
            {"tool_use_id": "t1", "result": "a"},
            {"tool_use_id": "t2", "result": "b"},
        ])
        assert len(results) == 2
        assert results[0]["tool_use_id"] == "t1"
        assert results[1]["tool_use_id"] == "t2"

    def test_build_single_tool_result(self):
        results = build_single_tool_result("t1", "done")
        assert len(results) == 1
        assert results[0]["tool_use_id"] == "t1"
        assert results[0]["content"] == "done"

    def test_build_single_tool_result_error(self):
        results = build_single_tool_result("t1", "fail", is_error=True)
        assert results[0]["is_error"] is True


# ===========================================================================
# Serialization
# ===========================================================================

class TestSerializeAnthropicObject:

    def test_none(self):
        assert _serialize_anthropic_object(None) is None

    def test_string(self):
        assert _serialize_anthropic_object("hello") == "hello"

    def test_int(self):
        assert _serialize_anthropic_object(42) == 42

    def test_bool(self):
        assert _serialize_anthropic_object(True) is True

    def test_list(self):
        assert _serialize_anthropic_object([1, "a"]) == [1, "a"]

    def test_dict(self):
        assert _serialize_anthropic_object({"k": "v"}) == {"k": "v"}

    def test_object_with_dict(self):
        obj = SimpleNamespace(type="text", text="hello")
        result = _serialize_anthropic_object(obj)
        assert result == {"type": "text", "text": "hello"}

    def test_skips_private_attributes(self):
        obj = SimpleNamespace(name="test", _internal="secret")
        result = _serialize_anthropic_object(obj)
        assert "name" in result
        assert "_internal" not in result

    def test_nested_object(self):
        inner = SimpleNamespace(url="https://x.com")
        outer = SimpleNamespace(type="citation", data=inner)
        result = _serialize_anthropic_object(outer)
        assert result["data"]["url"] == "https://x.com"


class TestSerializeContentBlocks:

    def test_sdk_text_block(self):
        blocks = [_sdk_text("hello")]
        result = serialize_content_blocks(blocks)
        assert result == [{"type": "text", "text": "hello"}]

    def test_sdk_text_with_citations(self):
        cit = SimpleNamespace(url="https://x.com", title="X", cited_text="stuff")
        block = _sdk_text("cited text", citations=[cit])
        result = serialize_content_blocks([block])
        assert "citations" in result[0]
        assert result[0]["citations"][0]["url"] == "https://x.com"

    def test_sdk_text_without_citations(self):
        """Text block without citations attr should not have citations key."""
        block = SimpleNamespace(type="text", text="plain")
        result = serialize_content_blocks([block])
        assert "citations" not in result[0]

    def test_sdk_tool_use_block(self):
        block = _sdk_tool_use("t1", "search", {"q": "test"})
        result = serialize_content_blocks([block])
        assert result[0] == {
            "type": "tool_use",
            "id": "t1",
            "name": "search",
            "input": {"q": "test"},
        }

    def test_sdk_server_tool_use_block(self):
        block = _sdk_server_tool_use("s1", "web_search", {"query": "AI"})
        result = serialize_content_blocks([block])
        assert result[0]["type"] == "server_tool_use"
        assert result[0]["name"] == "web_search"

    def test_dict_passthrough(self):
        block = {"type": "text", "text": "already dict"}
        result = serialize_content_blocks([block])
        assert result[0] is block

    def test_mixed_blocks(self):
        blocks = [
            _sdk_text("thinking"),
            _sdk_tool_use("t1", "search", {}),
            {"type": "text", "text": "dict block"},
        ]
        result = serialize_content_blocks(blocks)
        assert len(result) == 3
        assert result[0]["type"] == "text"
        assert result[1]["type"] == "tool_use"
        assert result[2]["type"] == "text"


# ===========================================================================
# Token usage / model
# ===========================================================================

class TestTokenUsageAndModel:

    def test_get_token_usage(self):
        resp = {"usage": {"input_tokens": 100, "output_tokens": 50}}
        usage = get_token_usage(resp)
        assert usage == {"input_tokens": 100, "output_tokens": 50}

    def test_get_token_usage_missing(self):
        assert get_token_usage({}) == {"input_tokens": 0, "output_tokens": 0}

    def test_get_model(self):
        assert get_model({"model": "claude-sonnet-4-6"}) == "claude-sonnet-4-6"

    def test_get_model_missing(self):
        assert get_model({}) == ""
