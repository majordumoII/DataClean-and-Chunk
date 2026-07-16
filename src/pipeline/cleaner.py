"""Text cleaning pipeline — normalises messy extracted text."""

import re


class TextCleaner:
    """Cleans raw text extracted from documents."""

    @staticmethod
    def clean(text: str) -> str:
        """Apply all cleaning steps in sequence."""
        text = TextCleaner._normalise_whitespace(text)
        text = TextCleaner._remove_page_numbers(text)
        text = TextCleaner._fix_hyphenation(text)
        text = TextCleaner._normalise_unicode(text)
        text = TextCleaner._strip_control_chars(text)
        return text.strip()

    @staticmethod
    def _normalise_whitespace(text: str) -> str:
        """Collapse multiple spaces/newlines into single ones."""
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    @staticmethod
    def _remove_page_numbers(text: str) -> str:
        """Remove standalone page numbers (common in PDFs)."""
        # Lines that are just a number (page markers)
        text = re.sub(r"^\d+\s*$", "", text, flags=re.MULTILINE)
        # "Page X of Y" patterns
        text = re.sub(r"(?i)page\s+\d+\s+of\s+\d+", "", text)
        return text

    @staticmethod
    def _fix_hyphenation(text: str) -> str:
        """Rejoin words broken across line breaks (e.g. 'docu-\nment')."""
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
        return text

    @staticmethod
    def _normalise_unicode(text: str) -> str:
        """Normalise unicode characters (smart quotes, dashes, etc.)."""
        replacements = {
            "\u201c": '"',
            "\u201d": '"',
            "\u2018": "'",
            "\u2019": "'",
            "\u2013": "-",
            "\u2014": "--",
            "\u2026": "...",
            "\u00a0": " ",  # non-breaking space
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    @staticmethod
    def _strip_control_chars(text: str) -> str:
        """Remove non-printable control characters except newlines/tabs."""
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
