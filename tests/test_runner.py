"""Tests for PipelineRunner (with mocked DocAI and GCS)."""

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.runner import PipelineRunner


@pytest.fixture
def mock_docai_document():
    """Return a minimal mock documentai.Document."""
    doc = MagicMock()
    doc.text = (
        "This is the extracted document text.\n\n"
        "It has multiple paragraphs.\n"
        "Page 1 of 5\n"
    )

    chunk1 = MagicMock()
    chunk1.chunk_id = "chunk_0"
    chunk1.content = "First chunk content"
    chunk1.page_span.page_start = 0
    chunk1.page_span.page_end = 1
    chunk1.source_block_ids = ["block_1"]

    chunk2 = MagicMock()
    chunk2.chunk_id = "chunk_1"
    chunk2.content = "Second chunk content"
    chunk2.page_span.page_start = 1
    chunk2.page_span.page_end = 2
    chunk2.source_block_ids = ["block_2"]

    doc.chunked_document.chunks = [chunk1, chunk2]
    return doc


class TestPipelineRunner:
    def test_init_creates_components(self, config):
        runner = PipelineRunner(config)
        assert runner.config == config
        assert runner.extractor is not None
        assert runner.cleaner is not None
        assert runner.chunker is not None
        assert runner.metadata is not None

    @patch("src.pipeline.runner.storage.Client")
    @patch("src.pipeline.runner.DocumentExtractor.extract")
    def test_process_file_returns_expected_structure(
        self, mock_extract, mock_storage, config, mock_docai_document
    ):
        mock_extract.return_value = mock_docai_document
        mock_client = MagicMock()
        mock_storage.return_value = mock_client

        runner = PipelineRunner(config)
        result = runner.process_file("gs://test-bucket/test.pdf")

        assert result["source"] == "gs://test-bucket/test.pdf"
        assert result["filename"] == "test.pdf"
        assert "raw_char_count" in result
        assert "cleaned_char_count" in result
        assert "metadata" in result
        assert "docai_chunks_count" in result
        assert "langchain_chunks_count" in result
        assert "docai_chunks" in result
        assert "langchain_chunks" in result
        assert len(result["docai_chunks"]) == 2
        assert result["docai_chunks"][0]["chunk_id"] == "chunk_0"

    @patch("src.pipeline.runner.storage.Client")
    @patch("src.pipeline.runner.DocumentExtractor.extract")
    def test_process_file_cleans_text(
        self, mock_extract, mock_storage, config, mock_docai_document
    ):
        mock_extract.return_value = mock_docai_document
        mock_client = MagicMock()
        mock_storage.return_value = mock_client

        runner = PipelineRunner(config)
        result = runner.process_file("gs://test-bucket/test.pdf")

        # Page numbers should be removed by cleaner
        assert "Page 1 of 5" not in result["langchain_chunks"][0]["content"]

    @patch("src.pipeline.runner.storage.Client")
    @patch("src.pipeline.runner.DocumentExtractor.extract")
    def test_process_file_and_upload(
        self, mock_extract, mock_storage, config, mock_docai_document
    ):
        mock_extract.return_value = mock_docai_document

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket
        mock_storage.return_value = mock_client

        runner = PipelineRunner(config)
        result = runner.process_file_and_upload(
            "gs://test-bucket/test.pdf"
        )

        assert "gs://" in result
        assert "test.json" in result
        mock_bucket.blob.assert_called_once()
        mock_blob.upload_from_string.assert_called_once()

    @patch("src.pipeline.runner.storage.Client")
    @patch("src.pipeline.runner.DocumentExtractor.extract")
    def test_process_bucket_prefix_no_pdfs(
        self, mock_extract, mock_storage, config
    ):
        mock_client = MagicMock()
        # No PDFs returned
        mock_client.bucket.return_value.list_blobs.return_value = []
        mock_storage.return_value = mock_client

        runner = PipelineRunner(config)
        results = runner.process_bucket_prefix(prefix="some-prefix/")

        assert results == []

    @patch("src.pipeline.runner.storage.Client")
    @patch("src.pipeline.runner.DocumentExtractor.extract")
    def test_process_bucket_prefix_detailed(
        self, mock_extract, mock_storage, config, mock_docai_document
    ):
        mock_extract.return_value = mock_docai_document

        # Mock one PDF blob returned by GCS
        blob = MagicMock()
        blob.configure_mock(name="docs/report.pdf")

        mock_client = MagicMock()
        mock_client.bucket.return_value.list_blobs.return_value = [blob]
        mock_storage.return_value = mock_client

        runner = PipelineRunner(config)
        results = runner.process_bucket_prefix_detailed(
            prefix="docs/", upload=False
        )

        assert len(results) == 1
        assert results[0]["filename"] == "report.pdf"
        assert results[0]["source"] == "gs://test-input-bucket/docs/report.pdf"

    @patch("src.pipeline.runner.storage.Client")
    @patch("src.pipeline.runner.DocumentExtractor.extract")
    def test_process_bucket_prefix_detailed_handles_errors(
        self, mock_extract, mock_storage, config
    ):
        mock_extract.side_effect = RuntimeError("DocAI failure")

        blob = MagicMock()
        blob.configure_mock(name="docs/broken.pdf")

        mock_client = MagicMock()
        mock_client.bucket.return_value.list_blobs.return_value = [blob]
        mock_storage.return_value = mock_client

        runner = PipelineRunner(config)
        results = runner.process_bucket_prefix_detailed(
            prefix="docs/", upload=False
        )

        # Should catch the error and return empty, not crash
        assert results == []
