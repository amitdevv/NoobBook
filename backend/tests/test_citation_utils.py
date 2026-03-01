"""
Tests for citation_utils.

Covers:
- parse_chunk_id: UUID with hyphens, valid/invalid formats
- extract_citations_from_text: single, multiple, dedup, no citations
"""
import pytest

from app.utils.citation_utils import (
    parse_chunk_id,
    extract_citations_from_text,
)


# ===========================================================================
# parse_chunk_id
# ===========================================================================

class TestParseChunkId:

    def test_uuid_with_hyphens(self):
        """UUIDs with hyphens are parsed correctly as source_id."""
        result = parse_chunk_id("abc123-def456_page_5_chunk_2")
        assert result is not None
        assert result["source_id"] == "abc123-def456"
        assert result["page_number"] == 5
        assert result["chunk_index"] == 2

    def test_full_uuid(self):
        result = parse_chunk_id("550e8400-e29b-41d4-a716-446655440000_page_1_chunk_1")
        assert result is not None
        assert result["source_id"] == "550e8400-e29b-41d4-a716-446655440000"

    def test_simple_source_id(self):
        result = parse_chunk_id("simple_page_1_chunk_1")
        assert result is not None
        assert result["source_id"] == "simple"
        assert result["page_number"] == 1
        assert result["chunk_index"] == 1

    def test_page_zero(self):
        result = parse_chunk_id("src_page_0_chunk_0")
        assert result is not None
        assert result["page_number"] == 0
        assert result["chunk_index"] == 0

    def test_large_numbers(self):
        result = parse_chunk_id("src_page_100_chunk_50")
        assert result is not None
        assert result["page_number"] == 100
        assert result["chunk_index"] == 50

    def test_malformed_no_page(self):
        assert parse_chunk_id("malformed") is None

    def test_empty_string(self):
        assert parse_chunk_id("") is None

    def test_partial_format_missing_chunk(self):
        assert parse_chunk_id("src_page_1") is None

    def test_partial_format_missing_page_number(self):
        assert parse_chunk_id("src_page__chunk_1") is None


# ===========================================================================
# extract_citations_from_text
# ===========================================================================

class TestExtractCitationsFromText:

    def test_single_citation(self):
        text = "The answer is 42 [[cite:src1_page_1_chunk_1]]."
        result = extract_citations_from_text(text)
        assert result == ["src1_page_1_chunk_1"]

    def test_multiple_citations(self):
        text = "First [[cite:a_page_1_chunk_1]] and second [[cite:b_page_2_chunk_3]]."
        result = extract_citations_from_text(text)
        assert len(result) == 2
        assert result[0] == "a_page_1_chunk_1"
        assert result[1] == "b_page_2_chunk_3"

    def test_deduplication(self):
        """Duplicate citations are returned only once, in order."""
        text = "First [[cite:x_page_1_chunk_1]] and again [[cite:x_page_1_chunk_1]]."
        result = extract_citations_from_text(text)
        assert result == ["x_page_1_chunk_1"]

    def test_preserves_order(self):
        text = "[[cite:c_page_1_chunk_1]] [[cite:a_page_1_chunk_1]] [[cite:b_page_1_chunk_1]]"
        result = extract_citations_from_text(text)
        assert result == ["c_page_1_chunk_1", "a_page_1_chunk_1", "b_page_1_chunk_1"]

    def test_no_citations(self):
        assert extract_citations_from_text("No citations here.") == []

    def test_empty_string(self):
        assert extract_citations_from_text("") == []

    def test_uuid_in_citation(self):
        """Citations with UUID source_ids (hyphens) are extracted correctly."""
        text = "Info [[cite:550e8400-e29b-41d4_page_3_chunk_2]]."
        result = extract_citations_from_text(text)
        assert result == ["550e8400-e29b-41d4_page_3_chunk_2"]

    def test_citation_in_middle_of_text(self):
        text = "The study shows [[cite:src_page_1_chunk_1]] that AI is growing."
        result = extract_citations_from_text(text)
        assert len(result) == 1
