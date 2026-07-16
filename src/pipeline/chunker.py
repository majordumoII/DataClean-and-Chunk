"""Semantic chunking via LangChain text splitters."""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import PipelineConfig


class SemanticChunker:
    """Splits cleaned text into semantic chunks for embedding/retrieval."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separators=["\n\n", "\n", ". ", "! ", "? ", ";", ",", " "],
            length_function=len,
            is_separator_regex=False,
        )

    def chunk(self, text: str, source: str | None = None) -> list[dict]:
        """Split text into chunks with source metadata."""
        chunks = self.splitter.create_documents([text])
        results = []
        for i, doc in enumerate(chunks):
            results.append(
                {
                    "chunk_index": i,
                    "content": doc.page_content,
                    "char_count": len(doc.page_content),
                    "source": source or "unknown",
                }
            )
        return results

    def chunk_with_overlap(self, text: str, source: str | None = None) -> list[dict]:
        """Alias for chunk — kept for explicit naming."""
        return self.chunk(text, source)
