"""
Tests for text/chunking.py — the RAG chunking pipeline.

Covers:
- parse_processed_text: multi-page, no markers, empty pages, chunk ID format
- _split_text_into_token_chunks: under/over max tokens
- _split_long_sentence: word-level splitting
- _split_into_sentences: sentence boundary detection
- chunks_to_pinecone_format: metadata keys, length mismatch guard
"""
import pytest
from unittest.mock import patch

from app.utils.text.chunking import (
    parse_processed_text,
    _split_text_into_token_chunks,
    _split_into_sentences,
    _split_long_sentence,
    chunks_to_pinecone_format,
    Chunk,
)


# ===========================================================================
# parse_processed_text
# ===========================================================================

class TestParseProcessedText:

    def test_empty_text(self):
        assert parse_processed_text("", "src1", "doc.pdf") == []

    def test_none_text(self):
        assert parse_processed_text(None, "src1", "doc.pdf") == []

    def test_no_markers_single_chunk(self):
        """Short text without markers → single chunk on page 1."""
        text = "This is a short piece of text."
        chunks = parse_processed_text(text, "src1", "doc.pdf")
        assert len(chunks) >= 1
        assert chunks[0].page_number == 1
        assert chunks[0].chunk_id == "src1_page_1_chunk_1"
        assert chunks[0].source_id == "src1"
        assert chunks[0].source_name == "doc.pdf"

    def test_single_page_marker(self):
        """Single page marker produces chunk(s) for that page."""
        text = "=== PDF PAGE 1 of 1 ===\n\nHello world content here."
        chunks = parse_processed_text(text, "src1", "report.pdf")
        assert len(chunks) >= 1
        assert chunks[0].page_number == 1
        assert chunks[0].chunk_id == "src1_page_1_chunk_1"

    def test_multi_page_correct_page_numbers(self):
        """Multiple page markers → chunks with correct page numbers."""
        text = (
            "=== PDF PAGE 1 of 3 ===\n\nPage one content.\n\n"
            "=== PDF PAGE 2 of 3 ===\n\nPage two content.\n\n"
            "=== PDF PAGE 3 of 3 ===\n\nPage three content.\n\n"
        )
        chunks = parse_processed_text(text, "abc-123", "book.pdf")
        page_numbers = [c.page_number for c in chunks]
        assert 1 in page_numbers
        assert 2 in page_numbers
        assert 3 in page_numbers

    def test_chunk_id_format(self):
        """Chunk IDs follow {source_id}_page_{N}_chunk_{M} format."""
        text = "=== TEXT PAGE 1 of 1 ===\n\nSome text."
        chunks = parse_processed_text(text, "my-uuid-123", "notes.txt")
        for chunk in chunks:
            assert chunk.chunk_id.startswith("my-uuid-123_page_")
            assert "_chunk_" in chunk.chunk_id

    def test_empty_page_skipped(self):
        """Page with only whitespace between markers is skipped."""
        text = (
            "=== PDF PAGE 1 of 3 ===\n\nContent here.\n\n"
            "=== PDF PAGE 2 of 3 ===\n\n   \n\n"
            "=== PDF PAGE 3 of 3 ===\n\nMore content.\n\n"
        )
        chunks = parse_processed_text(text, "src1", "doc.pdf")
        page_numbers = [c.page_number for c in chunks]
        assert 2 not in page_numbers

    def test_header_before_first_marker_ignored(self):
        """Header content before the first marker is ignored."""
        text = (
            "# Extracted from PDF document: report.pdf\n"
            "# Type: PDF\n"
            "# ---\n\n"
            "=== PDF PAGE 1 of 1 ===\n\nActual content."
        )
        chunks = parse_processed_text(text, "src1", "report.pdf")
        assert len(chunks) >= 1
        # Header metadata should not appear in chunk text
        assert "Extracted from" not in chunks[0].text

    def test_all_source_types_matched(self):
        """All standard source types produce valid chunks."""
        for src_type in ["PDF", "TEXT", "DOCX", "PPTX", "AUDIO", "LINK", "YOUTUBE", "IMAGE", "RESEARCH"]:
            text = f"=== {src_type} PAGE 1 of 1 ===\n\nContent for {src_type}."
            chunks = parse_processed_text(text, "src1", f"file.{src_type.lower()}")
            assert len(chunks) >= 1, f"No chunks for source type {src_type}"

    def test_uuid_with_hyphens_in_source_id(self):
        """Source IDs with hyphens (UUIDs) are preserved correctly in chunk IDs."""
        text = "=== PDF PAGE 1 of 1 ===\n\nContent."
        chunks = parse_processed_text(text, "abc-def-123-456", "doc.pdf")
        assert chunks[0].chunk_id.startswith("abc-def-123-456_page_")


# ===========================================================================
# _split_text_into_token_chunks
# ===========================================================================

class TestSplitTextIntoTokenChunks:

    def test_empty_text(self):
        assert _split_text_into_token_chunks("") == []

    def test_short_text_single_chunk(self):
        """Text under max tokens stays as one chunk."""
        text = "Short text here."
        result = _split_text_into_token_chunks(text)
        assert len(result) == 1
        assert result[0] == text

    def test_long_text_multiple_chunks(self):
        """Text exceeding max tokens is split into multiple chunks."""
        # Generate text that exceeds 240 tokens (~1 token per word roughly)
        words = [f"word{i}" for i in range(500)]
        text = " ".join(words)
        result = _split_text_into_token_chunks(text)
        assert len(result) > 1

    def test_all_content_preserved(self):
        """Splitting doesn't lose any words."""
        words = [f"word{i}" for i in range(300)]
        text = " ".join(words)
        result = _split_text_into_token_chunks(text)
        rejoined = " ".join(result)
        for word in words:
            assert word in rejoined


# ===========================================================================
# _split_into_sentences
# ===========================================================================

class TestSplitIntoSentences:

    def test_period_split(self):
        result = _split_into_sentences("First sentence. Second sentence.")
        assert len(result) == 2

    def test_question_mark_split(self):
        result = _split_into_sentences("What is AI? It is machine learning.")
        assert len(result) == 2

    def test_exclamation_split(self):
        result = _split_into_sentences("Wow! That is amazing.")
        assert len(result) == 2

    def test_preserves_punctuation(self):
        result = _split_into_sentences("Hello world. Goodbye.")
        assert result[0].endswith(".")
        assert result[1].endswith(".")

    def test_no_split_on_abbreviation_without_space(self):
        """No space after period → not split (e.g., 'Dr.Smith')."""
        result = _split_into_sentences("Dr.Smith is here.")
        assert len(result) == 1

    def test_empty_string(self):
        result = _split_into_sentences("")
        assert result == []


# ===========================================================================
# _split_long_sentence
# ===========================================================================

class TestSplitLongSentence:

    def test_splits_by_words(self):
        words = [f"w{i}" for i in range(200)]
        sentence = " ".join(words)
        result = _split_long_sentence(sentence, target_tokens=50, max_tokens=60)
        assert len(result) > 1

    def test_no_words_lost(self):
        words = [f"w{i}" for i in range(100)]
        sentence = " ".join(words)
        result = _split_long_sentence(sentence, target_tokens=30, max_tokens=40)
        rejoined = " ".join(result)
        for word in words:
            assert word in rejoined

    def test_single_word(self):
        result = _split_long_sentence("superlongword", target_tokens=5, max_tokens=10)
        assert len(result) == 1
        assert result[0] == "superlongword"


# ===========================================================================
# chunks_to_pinecone_format
# ===========================================================================

class TestChunksToPineconeFormat:

    def test_correct_format(self):
        chunks = [
            Chunk(text="hello", page_number=1, source_id="s1",
                  source_name="doc.pdf", chunk_id="s1_page_1_chunk_1", chunk_index=1),
        ]
        embeddings = [[0.1, 0.2, 0.3]]
        result = chunks_to_pinecone_format(chunks, embeddings)

        assert len(result) == 1
        vec = result[0]
        assert vec["id"] == "s1_page_1_chunk_1"
        assert vec["values"] == [0.1, 0.2, 0.3]
        assert vec["metadata"]["text"] == "hello"
        assert vec["metadata"]["page_number"] == 1
        assert vec["metadata"]["chunk_index"] == 1
        assert vec["metadata"]["source_id"] == "s1"
        assert vec["metadata"]["source_name"] == "doc.pdf"

    def test_metadata_keys_present(self):
        """All required metadata keys are present for Pinecone queries."""
        chunks = [
            Chunk(text="t", page_number=2, source_id="s",
                  source_name="n", chunk_id="id", chunk_index=3),
        ]
        result = chunks_to_pinecone_format(chunks, [[0.0]])
        required_keys = {"text", "page_number", "chunk_index", "source_id", "source_name"}
        assert required_keys == set(result[0]["metadata"].keys())

    def test_length_mismatch_raises(self):
        chunks = [
            Chunk(text="a", page_number=1, source_id="s",
                  source_name="n", chunk_id="id1", chunk_index=1),
        ]
        with pytest.raises(ValueError, match="mismatch"):
            chunks_to_pinecone_format(chunks, [[0.1], [0.2]])

    def test_empty_lists(self):
        assert chunks_to_pinecone_format([], []) == []
