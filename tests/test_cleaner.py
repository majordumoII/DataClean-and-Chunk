"""Tests for TextCleaner."""

from src.pipeline.cleaner import TextCleaner


class TestTextCleaner:
    def test_clean_normalises_whitespace(self):
        result = TextCleaner.clean("Hello     world.\n\n\n\nNext para.")
        assert result == "Hello world.\n\nNext para."

    def test_clean_removes_page_numbers(self):
        text = "Some text\n42\nMore text"
        result = TextCleaner.clean(text)
        assert "42\n" not in result

    def test_clean_removes_page_x_of_y(self):
        text = "Some text\nPage 3 of 10\nMore text"
        result = TextCleaner.clean(text)
        assert "Page 3 of 10" not in result

    def test_clean_fixes_hyphenation(self):
        text = "This is a hyphen-\nated word."
        result = TextCleaner.clean(text)
        assert "hyphenated" in result
        assert "hyphen-\nated" not in result

    def test_clean_normalises_unicode(self):
        text = 'Smart \u201cquotes\u201d and em\u2014dash and non\u00a0breaking'
        result = TextCleaner.clean(text)
        assert '\u201c' not in result
        assert '\u201d' not in result
        assert '\u2014' not in result
        assert '\u00a0' not in result
        assert '"' in result
        assert '--' in result
        assert ' ' in result

    def test_clean_strips_control_chars(self):
        text = "Hello\x00world\x1f!"
        result = TextCleaner.clean(text)
        assert result == "Helloworld!"

    def test_empty_string(self):
        assert TextCleaner.clean("") == ""

    def test_only_whitespace(self):
        assert TextCleaner.clean("   \n\n  ") == ""

    def test_clean_strips_result(self):
        result = TextCleaner.clean("  Hello world.  ")
        assert result == "Hello world."
        assert result == result.strip()

    def test_normalise_whitespace_collapses_tabs(self):
        result = TextCleaner._normalise_whitespace("a\t\tb")
        assert result == "a b"

    def test_normalise_whitespace_handles_crlf(self):
        result = TextCleaner._normalise_whitespace("line1\r\nline2")
        assert result == "line1\nline2"

    def test_remove_page_numbers_multiline(self):
        text = "Header\n123\n456\nFooter"
        result = TextCleaner._remove_page_numbers(text)
        lines = [l for l in result.splitlines() if l.strip()]
        assert "123" not in lines
        assert "456" not in lines
        assert "Header" in lines
        assert "Footer" in lines

    def test_fix_hyphenation_no_change(self):
        text = "Normal text without breaks."
        assert TextCleaner._fix_hyphenation(text) == text

    def test_normalise_unicode_all_replacements(self):
        text = '\u201c\u201d\u2018\u2019\u2013\u2014\u2026'
        result = TextCleaner._normalise_unicode(text)
        assert result == '""\'\'---...'

    def test_strip_control_chars_preserves_newline_tab(self):
        text = "hello\nworld\t!"
        assert TextCleaner._strip_control_chars(text) == text
