"""Tests for MetadataExtractor."""

from src.pipeline.metadata import MetadataExtractor


class TestMetadataExtractor:
    def test_extract_basic_fields(self):
        meta = MetadataExtractor.extract("Hello world.", filename="test.txt")
        assert meta["filename"] == "test.txt"
        assert meta["char_count"] == 12
        assert meta["word_count"] == 2
        assert meta["line_count"] == 1

    def test_extract_default_filename(self):
        meta = MetadataExtractor.extract("Hello.")
        assert meta["filename"] == "unknown"

    def test_extract_includes_timestamp(self):
        meta = MetadataExtractor.extract("Hello.")
        assert meta["extracted_at"].endswith("Z")

    def test_detect_tables_true(self, sample_text_with_tables):
        assert MetadataExtractor._detect_tables(sample_text_with_tables) is True

    def test_detect_tables_false(self):
        assert MetadataExtractor._detect_tables("No pipes here.") is False

    def test_detect_tables_fewer_than_4_pipes(self):
        text = "a | b\nno pipes here"
        assert MetadataExtractor._detect_tables(text) is False

    def test_detect_lists_bullets(self, sample_text_with_lists):
        assert MetadataExtractor._detect_lists(sample_text_with_lists) is True

    def test_detect_lists_numbered(self):
        text = "1. First\n2. Second"
        assert MetadataExtractor._detect_lists(text) is True

    def test_detect_lists_false(self):
        assert MetadataExtractor._detect_lists("Plain text.") is False

    def test_detect_numbers_currency(self):
        assert MetadataExtractor._detect_numbers("Cost: $1,234.56") is True

    def test_detect_numbers_percentage(self):
        assert MetadataExtractor._detect_numbers("Growth: 15%") is True

    def test_detect_numbers_year(self):
        assert MetadataExtractor._detect_numbers("Year 2024 results") is True

    def test_detect_numbers_false(self):
        assert MetadataExtractor._detect_numbers("No numbers here.") is False

    def test_detect_language_english(self):
        text = "The cat and the dog are in the house with the ball and the toy."
        assert MetadataExtractor._detect_language(text) == "en"

    def test_detect_language_too_short(self):
        assert MetadataExtractor._detect_language("Hi") == "unknown"

    def test_detect_language_unknown(self):
        text = "Lorem ipsum dolor sit amet consectetur."
        assert MetadataExtractor._detect_language(text) == "unknown"

    def test_has_tables_in_extract(self, sample_text_with_tables):
        meta = MetadataExtractor.extract(sample_text_with_tables, "table.txt")
        assert meta["has_tables"] is True

    def test_has_lists_in_extract(self, sample_text_with_lists):
        meta = MetadataExtractor.extract(sample_text_with_lists, "list.txt")
        assert meta["has_lists"] is True

    def test_has_numbers_in_extract(self):
        meta = MetadataExtractor.extract("Revenue was $100k in 2024.")
        assert meta["has_numbers"] is True
