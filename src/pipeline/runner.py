"""Pipeline orchestrator — ties extraction → cleaning → chunking → metadata."""

import json
import logging
import os
from pathlib import Path

from google.cloud import storage

from .cleaner import TextCleaner
from .config import PipelineConfig
from .extractor import DocumentExtractor
from .metadata import MetadataExtractor
from .chunker import SemanticChunker

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Orchestrates the full document processing pipeline."""

    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig.from_env()
        self.extractor = DocumentExtractor(self.config)
        self.cleaner = TextCleaner()
        self.chunker = SemanticChunker(self.config)
        self.metadata = MetadataExtractor()
        self.storage_client = storage.Client(project=self.config.project_id)

    def process_file(self, gcs_uri: str, mime_type: str = "application/pdf") -> dict:
        """Run the full pipeline on a single file."""
        filename = os.path.basename(gcs_uri)
        logger.info("Processing %s ...", filename)

        # Step 1: Extract via DocAI Layout Parser (single API call)
        logger.info("  Extracting text via DocAI ...")
        doc = self.extractor.extract(gcs_uri, mime_type)
        raw_text = self.extractor._text_from_document(doc)
        docai_chunks = self.extractor._chunks_from_document(doc)
        logger.info("  Got %d chars and %d DocAI chunks", len(raw_text), len(docai_chunks))

        # Step 2: Clean the extracted text
        logger.info("  Cleaning text ...")
        cleaned_text = self.cleaner.clean(raw_text)

        # Step 3: LangChain semantic chunking
        logger.info("  Semantic chunking via LangChain ...")
        lc_chunks = self.chunker.chunk(cleaned_text, source=filename)

        # Step 4: Extract metadata
        logger.info("  Extracting metadata ...")
        meta = self.metadata.extract(cleaned_text, filename=filename)

        result = {
            "source": gcs_uri,
            "filename": filename,
            "raw_char_count": len(raw_text),
            "cleaned_char_count": len(cleaned_text),
            "metadata": meta,
            "docai_chunks_count": len(docai_chunks),
            "langchain_chunks_count": len(lc_chunks),
            "docai_chunks": docai_chunks,
            "langchain_chunks": lc_chunks,
        }
        return result

    def process_file_and_upload(
        self, gcs_uri: str, mime_type: str = "application/pdf"
    ) -> str:
        """Process a file and upload the result JSON to the output bucket."""
        result = self.process_file(gcs_uri, mime_type)
        output_filename = result["filename"].rsplit(".", 1)[0] + ".json"
        output_path = f"results/{output_filename}"

        bucket = self.storage_client.bucket(self.config.output_bucket)
        blob = bucket.blob(output_path)
        blob.upload_from_string(
            json.dumps(result, indent=2), content_type="application/json"
        )
        logger.info("Uploaded results to gs://%s/%s", self.config.output_bucket, output_path)
        return f"gs://{self.config.output_bucket}/{output_path}"

    def process_bucket_prefix(self, prefix: str = "") -> list[str]:
        """Process all PDFs in the input bucket under a given prefix."""
        bucket = self.storage_client.bucket(self.config.input_bucket)
        blobs = bucket.list_blobs(prefix=prefix)
        pdf_blobs = [b for b in blobs if b.name.lower().endswith(".pdf")]

        if not pdf_blobs:
            logger.warning("No PDFs found under gs://%s/%s", self.config.input_bucket, prefix)
            return []

        results = []
        for blob in pdf_blobs:
            gcs_uri = f"gs://{self.config.input_bucket}/{blob.name}"
            try:
                output = self.process_file_and_upload(gcs_uri)
                results.append(output)
            except Exception as e:
                logger.error("Failed to process %s: %s", gcs_uri, e)
        return results
