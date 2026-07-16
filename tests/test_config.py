"""Tests for PipelineConfig."""

import os

from src.pipeline.config import PipelineConfig


class TestPipelineConfig:
    def test_defaults_when_no_env(self):
        """Should use sensible defaults when env vars aren't set."""
        saved = {}
        keys = [
            "GOOGLE_CLOUD_PROJECT", "DOCAI_LOCATION", "DOCAI_PROCESSOR_ID",
            "INPUT_BUCKET", "OUTPUT_BUCKET", "CHUNK_SIZE", "CHUNK_OVERLAP",
            "PG_CONNECTION_STRING", "VECTOR_TABLE",
        ]
        for k in keys:
            saved[k] = os.environ.pop(k, None)

        try:
            cfg = PipelineConfig()
            assert cfg.project_id == ""
            assert cfg.location == "us"
            assert cfg.processor_id == ""
            assert cfg.input_bucket == "corporate-raw-docs"
            assert cfg.output_bucket == "corporate-processed-docs"
            assert cfg.chunk_size == 1024
            assert cfg.chunk_overlap == 200
            assert cfg.pg_connection_string == ""
            assert cfg.vector_table == "document_chunks"
        finally:
            os.environ.update({k: v for k, v in saved.items() if v is not None})

    def test_from_env_loads_vars(self, mock_env):
        cfg = PipelineConfig.from_env()
        assert cfg.project_id == "test-project"
        assert cfg.location == "us"
        assert cfg.processor_id == "test-processor"
        assert cfg.input_bucket == "test-input-bucket"
        assert cfg.output_bucket == "test-output-bucket"
        assert cfg.chunk_size == 512
        assert cfg.chunk_overlap == 64
        assert cfg.pg_connection_string == "postgresql://user:pass@localhost:5432/testdb"
        assert cfg.vector_table == "test_chunks"

    def test_processor_version(self, config):
        assert config.processor_version.startswith("pretrained-layout-parser")
        assert "v1.5" in config.processor_version
