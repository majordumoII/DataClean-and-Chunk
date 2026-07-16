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
        self.client = documentai.DocumentProcessorServiceClient(client_options=opts)

    @property
    def _processor_name(self) -> str:
        return self.client.processor_path(
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

    def extract_text(self, gcs_uri: str, mime_type: str = "application/pdf") -> str:
        """Extract raw text content from a document."""
        doc = self.extract(gcs_uri, mime_type)
        return doc.text

    def extract_chunks(self, gcs_uri: str, mime_type: str = "application/pdf") -> list[dict]:
        """Extract RAG-ready chunks with metadata."""
        doc = self.extract(gcs_uri, mime_type)
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
