"""Metadata extraction from documents."""

import re
from datetime import datetime, timezone


class MetadataExtractor:
    """Extracts structural metadata from document text."""

    @staticmethod
    def extract(text: str, filename: str | None = None) -> dict:
        """Extract metadata from document text."""
        return {
            "filename": filename or "unknown",
            "char_count": len(text),
            "word_count": len(text.split()),
            "line_count": len(text.splitlines()),
            "has_tables": MetadataExtractor._detect_tables(text),
            "has_lists": MetadataExtractor._detect_lists(text),
            "has_numbers": MetadataExtractor._detect_numbers(text),
            "extracted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "language": MetadataExtractor._detect_language(text),
        }

    @staticmethod
    def _detect_tables(text: str) -> bool:
        """Naive table detection — looks for pipe/column-like patterns."""
        lines = text.splitlines()
        pipe_count = sum(1 for line in lines if "|" in line)
        return pipe_count > 3

    @staticmethod
    def _detect_lists(text: str) -> bool:
        """Detect bullet or numbered lists."""
        bullet_pattern = re.compile(r"^[\s]*[-*•]\s", re.MULTILINE)
        numbered_pattern = re.compile(r"^[\s]*\d+[.)]\s", re.MULTILINE)
        return bool(bullet_pattern.search(text) or numbered_pattern.search(text))

    @staticmethod
    def _detect_numbers(text: str) -> bool:
        """Check if text contains numeric data (currency, percentages, etc.)."""
        number_pattern = re.compile(
            r"\$\d+[\d,]*\.?\d*|[\d,]+\s?%|\b\d{4}\b"
        )
        return bool(number_pattern.search(text))

    @staticmethod
    def _detect_language(text: str) -> str:
        """Simple language detection via common words."""
        # Very basic heuristic — upgrade to langdetect lib if needed
        english_indicators = ["the", "and", "is", "in", "it", "of", "to", "a"]
        words = text.lower().split()
        if len(words) < 10:
            return "unknown"
        en_score = sum(1 for w in words if w in english_indicators)
        return "en" if en_score > len(words) * 0.05 else "unknown"
