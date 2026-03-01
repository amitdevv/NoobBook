"""
Tests for text utilities: processed_output, cleaning, page_markers.

Covers:
- build_processed_output: header format, page markers, empty pages, source type casing
- _format_token_count: None, boundary values, invalid strings
- clean_text_for_embedding: whitespace normalization, empty/None input
- clean_chunk_text: header stripping, no-header fallback
- normalize_whitespace: paragraph preservation
- build_page_marker: format string, case handling
- find_all_markers: multi-page, no markers, all source types
"""
import pytest

from app.utils.text.processed_output import (
    build_processed_output,
    _format_token_count,
    SOURCE_METADATA_KEYS,
)
from app.utils.text.cleaning import (
    clean_text_for_embedding,
    clean_chunk_text,
    normalize_whitespace,
)
from app.utils.text.page_markers import (
    build_page_marker,
    find_all_markers,
    get_page_number,
    get_total_pages,
    SOURCE_TYPES,
    ANY_PAGE_PATTERN,
)


# ===========================================================================
# _format_token_count
# ===========================================================================

class TestFormatTokenCount:

    def test_none_returns_200k_plus(self):
        assert _format_token_count(None) == "200k+"

    def test_under_limit(self):
        assert _format_token_count(150000) == "150000"

    def test_at_limit(self):
        assert _format_token_count(200000) == "200000"

    def test_over_limit(self):
        assert _format_token_count(250000) == "200k+"

    def test_zero(self):
        assert _format_token_count(0) == "0"

    def test_string_passthrough(self):
        assert _format_token_count("200k+") == "200k+"

    def test_invalid_string(self):
        assert _format_token_count("abc") == "200k+"

    def test_string_number(self):
        assert _format_token_count("5000") == "5000"


# ===========================================================================
# build_processed_output
# ===========================================================================

class TestBuildProcessedOutput:

    def test_empty_pages(self):
        assert build_processed_output([], "PDF") == ""

    def test_header_contains_type(self):
        result = build_processed_output(["page1"], "PDF", "report.pdf")
        assert "# Type: PDF" in result

    def test_header_contains_source_name(self):
        result = build_processed_output(["page1"], "PDF", "report.pdf")
        assert "report.pdf" in result

    def test_header_ends_with_separator(self):
        """Header must end with '# ---' for downstream parsing."""
        result = build_processed_output(["page1"], "PDF", "test.pdf")
        # Find the separator
        assert "# ---\n" in result

    def test_page_markers_present(self):
        result = build_processed_output(["p1", "p2"], "PDF", "doc.pdf")
        assert "=== PDF PAGE 1 of 2 ===" in result
        assert "=== PDF PAGE 2 of 2 ===" in result

    def test_lowercase_source_type_uppercased(self):
        """Lowercase source type input produces UPPERCASE markers."""
        result = build_processed_output(["content"], "pdf", "doc.pdf")
        assert "=== PDF PAGE 1 of 1 ===" in result
        assert "# Type: PDF" in result

    def test_metadata_keys_present(self):
        """All required metadata keys for PDF type are in header."""
        meta = {"model_used": "claude-sonnet", "character_count": 100, "token_count": 25}
        result = build_processed_output(["page1"], "PDF", "doc.pdf", meta)
        assert "# model_used: claude-sonnet" in result
        assert "# character_count: 100" in result
        assert "# token_count: 25" in result

    def test_missing_metadata_uses_empty(self):
        """Missing metadata values default to empty string."""
        result = build_processed_output(["page1"], "PDF", "doc.pdf", {})
        assert "# model_used: \n" in result

    def test_unknown_source_type_uses_fallback_keys(self):
        """Unknown source type uses character_count + token_count fallback."""
        result = build_processed_output(["page1"], "CUSTOM", "file.xyz")
        assert "# character_count:" in result
        assert "# token_count:" in result

    def test_page_content_included(self):
        result = build_processed_output(["Hello world"], "TEXT", "notes.txt")
        assert "Hello world" in result

    def test_multiple_pages_content(self):
        result = build_processed_output(["Page one.", "Page two."], "PDF", "doc.pdf")
        assert "Page one." in result
        assert "Page two." in result


# ===========================================================================
# clean_text_for_embedding
# ===========================================================================

class TestCleanTextForEmbedding:

    def test_empty_string(self):
        assert clean_text_for_embedding("") == ""

    def test_none_input(self):
        assert clean_text_for_embedding(None) == ""

    def test_strips_leading_trailing(self):
        assert clean_text_for_embedding("  hello  ") == "hello"

    def test_collapses_multiple_newlines(self):
        result = clean_text_for_embedding("a\n\n\n\nb")
        assert result == "a\nb"

    def test_collapses_double_newlines(self):
        result = clean_text_for_embedding("a\n\nb")
        assert result == "a\nb"

    def test_collapses_multiple_spaces(self):
        result = clean_text_for_embedding("a     b")
        assert result == "a b"

    def test_preserves_single_newline(self):
        result = clean_text_for_embedding("a\nb")
        assert result == "a\nb"

    def test_mixed_whitespace(self):
        """Newlines collapse first, then spaces collapse."""
        result = clean_text_for_embedding("  a  \n\n\n  b   c  ")
        # "  a  \n\n\n  b   c  " → strip → "a  \n\n\n  b   c"
        # → collapse newlines → "a  \n  b   c" → collapse spaces → "a \n b c"
        assert result == "a \n b c"


# ===========================================================================
# clean_chunk_text
# ===========================================================================

class TestCleanChunkText:

    def test_empty_string(self):
        assert clean_chunk_text("") == ""

    def test_none_input(self):
        assert clean_chunk_text(None) == ""

    def test_strips_metadata_header(self):
        text = "# Chunk Metadata\n# source_id: abc\n# ---\n\nActual content here."
        result = clean_chunk_text(text)
        assert "Chunk Metadata" not in result
        assert "Actual content" in result

    def test_no_header_cleans_normally(self):
        text = "Just regular   text   here."
        result = clean_chunk_text(text)
        assert result == "Just regular text here."

    def test_header_without_separator(self):
        """Header present but no '# ---' → full text is cleaned (including header lines)."""
        text = "# Chunk Metadata\n# source_id: abc\n\nContent after."
        result = clean_chunk_text(text)
        # Header is NOT stripped because separator is missing
        assert "Chunk Metadata" in result


# ===========================================================================
# normalize_whitespace
# ===========================================================================

class TestNormalizeWhitespace:

    def test_empty_string(self):
        assert normalize_whitespace("") == ""

    def test_none_input(self):
        assert normalize_whitespace(None) == ""

    def test_preserves_double_newlines(self):
        result = normalize_whitespace("para1\n\npara2")
        assert result == "para1\n\npara2"

    def test_collapses_triple_newlines(self):
        result = normalize_whitespace("a\n\n\nb")
        assert result == "a\n\nb"

    def test_collapses_many_newlines(self):
        result = normalize_whitespace("a\n\n\n\n\n\nb")
        assert result == "a\n\nb"

    def test_collapses_spaces(self):
        result = normalize_whitespace("a     b")
        assert result == "a b"


# ===========================================================================
# build_page_marker
# ===========================================================================

class TestBuildPageMarker:

    def test_basic_format(self):
        assert build_page_marker("PDF", 1, 5) == "=== PDF PAGE 1 of 5 ==="

    def test_uppercase_conversion(self):
        assert build_page_marker("pdf", 3, 10) == "=== PDF PAGE 3 of 10 ==="

    def test_single_page(self):
        assert build_page_marker("TEXT", 1, 1) == "=== TEXT PAGE 1 of 1 ==="

    def test_youtube(self):
        assert build_page_marker("YOUTUBE", 1, 1) == "=== YOUTUBE PAGE 1 of 1 ==="


# ===========================================================================
# find_all_markers / regex
# ===========================================================================

class TestFindAllMarkers:

    def test_single_marker(self):
        text = "=== PDF PAGE 1 of 5 ===\n\ncontent"
        markers = find_all_markers(text)
        assert len(markers) == 1
        assert get_page_number(markers[0]) == 1
        assert get_total_pages(markers[0]) == 5

    def test_multiple_markers(self):
        text = "=== PDF PAGE 1 of 3 ===\np1\n=== PDF PAGE 2 of 3 ===\np2\n=== PDF PAGE 3 of 3 ===\np3"
        markers = find_all_markers(text)
        assert len(markers) == 3

    def test_no_markers(self):
        assert find_all_markers("Just plain text") == []

    def test_empty_string(self):
        assert find_all_markers("") == []

    def test_malformed_marker_not_matched(self):
        """Missing 'of N' part should not match."""
        assert find_all_markers("=== PDF PAGE 1 ===") == []

    def test_all_source_types_matched(self):
        """Every registered source type is matched by ANY_PAGE_PATTERN."""
        for src_type in SOURCE_TYPES:
            marker = f"=== {src_type} PAGE 1 of 1 ==="
            matches = find_all_markers(marker)
            assert len(matches) == 1, f"Pattern did not match source type: {src_type}"

    def test_marker_with_optional_suffix(self):
        """Markers with optional suffixes like '(continues...)' are matched."""
        text = "=== PDF PAGE 1 of 5 (continues...) ==="
        markers = find_all_markers(text)
        assert len(markers) == 1
