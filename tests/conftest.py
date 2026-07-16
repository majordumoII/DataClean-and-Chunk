"""Shared fixtures for all pipeline tests."""

import os
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.config import PipelineConfig


@pytest.fixture
def mock_env() -> Generator[None, None, None]:
    """Set common test env vars and restore after."""
    env_vars = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "DOCAI_LOCATION": "us",
        "DOCAI_PROCESSOR_ID": "test-processor",
        "INPUT_BUCKET": "test-input-bucket",
        "OUTPUT_BUCKET": "test-output-bucket",
        "CHUNK_SIZE": "512",
        "CHUNK_OVERLAP": "64",
        "EMBEDDING_MODEL": "text-embedding-005",
        "EMBEDDING_DIMENSIONS": "768",
        "PG_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/testdb",
        "VECTOR_TABLE": "test_chunks",
    }
    saved = {k: os.environ.get(k) for k in env_vars}
    os.environ.update(env_vars)
    yield
    for k in env_vars:
        if saved[k] is not None:
            os.environ[k] = saved[k]
        else:
            os.environ.pop(k, None)


@pytest.fixture
def config(mock_env: None) -> PipelineConfig:
    """A PipelineConfig loaded from test env vars."""
    return PipelineConfig.from_env()


@pytest.fixture
def sample_text() -> str:
    return (
        "This is a sample document. It has multiple sentences.\n\n"
        "It also has a second paragraph with some content.\n"
        "Page 1 of 10\n"
        "Here is a hyphen-\nated word to fix.\n"
    )


@pytest.fixture
def sample_text_with_tables() -> str:
    return (
        "Header\n\n"
        "| Name | Age | City |\n"
        "|------|-----|------|\n"
        "| Alice | 30 | NY |\n"
        "| Bob | 25 | SF |\n"
        "| Carol | 35 | LA |\n"
        "\nFooter text"
    )


@pytest.fixture
def sample_text_with_lists() -> str:
    return (
        "Shopping list:\n"
        "- Apples\n"
        "- Bananas\n"
        "- Cherries\n"
        "Steps:\n"
        "1. First do this\n"
        "2. Then do that"
    )


@pytest.fixture
def mock_storage_client() -> MagicMock:
    """A fully mocked GCS storage client."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket
    return mock_client
