"""Document AI Layout Parser wrapper — extracts text, tables, and images."""

from google.api_core.client_options import ClientOptions
from google.cloud import documentai

from .config import PipelineConfig


class DocumentExtractor:
    def __init__(self, config: PipelineConfig):
        self.config = config
        opts = ClientOptions(
            api_endpoint=f"{config.location}-documentai.googleapis.com"
        )
        # REST transport works reliably with processor version paths
        self.client = documentai.DocumentProcessorServiceClient(
            client_options=opts, transport="rest"
        )

    @property
    def _processor_name(self) -> str:
        """Full processor version resource path."""
        return self.client.processor_version_path(
            self.config.project_id,
            self.config.location,
            self.config.processor_id,
            self.config.processor_version,
        )

    def extract(self, gcs_uri: str, mime_type: str = "application/pdf") -> documentai.Document:
        """Process a single document via DocAI Layout Parser."""
        gcs_document = documentai.GcsDocument(gcs_uri=gcs_uri, mime_type=mime_type)
        process_options = documentai.ProcessOptions(
            layout_config=documentai.ProcessOptions.LayoutConfig(
                enable_table_annotation=True,
                enable_image_annotation=True,
                chunking_config=documentai.ProcessOptions.LayoutConfig.ChunkingConfig(
                    chunk_size=self.config.chunk_size,
                    include_ancestor_headings=True,
                ),
            ),
        )
        request = documentai.ProcessRequest(
            name=self._processor_name,
            gcs_document=gcs_document,
            process_options=process_options,
        )
        result = self.client.process_document(request=request)
        return result.document

    @staticmethod
    def _text_from_document(doc: documentai.Document) -> str:
        """Extract text from a Document object, falling back to chunk content."""
        if doc.text:
            return doc.text
        chunks = doc.chunked_document.chunks
        if chunks:
            return "\n\n".join(c.content for c in chunks)
        return ""

    @staticmethod
    def _chunks_from_document(doc: documentai.Document) -> list[dict]:
        """Extract RAG-ready chunk metadata from a Document object."""
        chunks = []
        for i, chunk in enumerate(doc.chunked_document.chunks):
            chunks.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "page_start": chunk.page_span.page_start,
                    "page_end": chunk.page_span.page_end,
                    "source_block_ids": list(chunk.source_block_ids),
                }
            )
        return chunks

    def extract_text(self, gcs_uri: str, mime_type: str = "application/pdf") -> str:
        """Extract raw text content from a document (single-use convenience)."""
        return self._text_from_document(self.extract(gcs_uri, mime_type))

    def extract_chunks(self, gcs_uri: str, mime_type: str = "application/pdf") -> list[dict]:
        """Extract RAG-ready chunks with metadata (single-use convenience)."""
        return self._chunks_from_document(self.extract(gcs_uri, mime_type))
