"""Tests for SemanticChunker."""

import pytest

from src.pipeline.chunker import SemanticChunker


class TestSemanticChunker:
    def test_chunk_single_short_text(self, config):
        chunker = SemanticChunker(config)
        result = chunker.chunk("Hello world.", source="test.txt")
        assert len(result) >= 1
        assert result[0]["content"] == "Hello world."
        assert result[0]["chunk_index"] == 0
        assert result[0]["source"] == "test.txt"
        assert result[0]["char_count"] == 12

    def test_chunk_splits_long_text(self, config):
        chunker = SemanticChunker(config)
        # config uses chunk_size=512 from mock_env
        long_text = " ".join(["word"] * 500)
        result = chunker.chunk(long_text, source="long.txt")
        assert len(result) > 1
        for chunk in result:
            assert chunk["source"] == "long.txt"
            assert "chunk_index" in chunk
            assert "content" in chunk
            assert "char_count" in chunk

    def test_chunk_default_source(self, config):
        chunker = SemanticChunker(config)
        result = chunker.chunk("Some text.")
        assert result[0]["source"] == "unknown"

    def test_chunk_returns_sequential_indices(self, config):
        chunker = SemanticChunker(config)
        long_text = "\n\n".join([f"Paragraph {i}." for i in range(20)])
        result = chunker.chunk(long_text)
        indices = [c["chunk_index"] for c in result]
        assert indices == list(range(len(result)))

    def test_chunk_preserves_content(self, config):
        chunker = SemanticChunker(config)
        text = "The quick brown fox jumps over the lazy dog."
        result = chunker.chunk(text)
        assert result[0]["content"] == text

    def test_chunk_empty_string(self, config):
        chunker = SemanticChunker(config)
        result = chunker.chunk("")
        # An empty string may produce 0 or 1 chunk depending on splitter
        assert isinstance(result, list)

    def test_chunk_with_overlap_alias(self, config):
        chunker = SemanticChunker(config)
        text = "Same text for both calls."
        r1 = chunker.chunk(text)
        r2 = chunker.chunk_with_overlap(text)
        assert r1 == r2
