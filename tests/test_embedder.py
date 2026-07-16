"""Tests for Embedder (with mocked Vertex AI)."""

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.embedder import Embedder


class TestEmbedder:
    @patch("src.pipeline.embedder.aiplatform.init")
    def test_init_calls_aiplatform(self, mock_init, config):
        Embedder(config)
        mock_init.assert_called_once_with(
            project=config.project_id, location=config.location
        )

    @patch("src.pipeline.embedder.aiplatform.init")
    @patch("vertexai.language_models.TextEmbeddingModel")
    def test_embed_returns_vector(self, mock_model_cls, mock_init, config):
        mock_instance = MagicMock()
        mock_model_cls.from_pretrained.return_value = mock_instance

        fake_embedding = MagicMock()
        fake_embedding.values = [0.1, 0.2, 0.3]
        mock_instance.get_embeddings.return_value = [fake_embedding]

        embedder = Embedder(config)
        result = embedder.embed("Hello world")

        assert result == [0.1, 0.2, 0.3]
        mock_instance.get_embeddings.assert_called_once_with(["Hello world"])

    @patch("src.pipeline.embedder.aiplatform.init")
    @patch("vertexai.language_models.TextEmbeddingModel")
    def test_embed_batch_returns_multiple_vectors(
        self, mock_model_cls, mock_init, config
    ):
        mock_instance = MagicMock()
        mock_model_cls.from_pretrained.return_value = mock_instance

        fake_embeddings = [
            MagicMock(values=[0.1, 0.2]),
            MagicMock(values=[0.3, 0.4]),
        ]
        mock_instance.get_embeddings.return_value = fake_embeddings

        embedder = Embedder(config)
        result = embedder.embed_batch(["Hello", "World"])

        assert result == [[0.1, 0.2], [0.3, 0.4]]
        mock_instance.get_embeddings.assert_called_once_with(["Hello", "World"])

    @patch("src.pipeline.embedder.aiplatform.init")
    @patch("vertexai.language_models.TextEmbeddingModel")
    def test_embed_empty_string(self, mock_model_cls, mock_init, config):
        mock_instance = MagicMock()
        mock_model_cls.from_pretrained.return_value = mock_instance
        fake_embedding = MagicMock(values=[])
        mock_instance.get_embeddings.return_value = [fake_embedding]

        embedder = Embedder(config)
        result = embedder.embed("")
        assert result == []

    @patch("src.pipeline.embedder.aiplatform.init")
    @patch("vertexai.language_models.TextEmbeddingModel")
    def test_model_lazy_loaded(self, mock_model_cls, mock_init, config):
        embedder = Embedder(config)
        assert embedder._model is None

        _ = embedder.model
        mock_model_cls.from_pretrained.assert_called_once_with(
            config.embedding_model_name
        )

        # Second access uses cached model
        _ = embedder.model
        assert mock_model_cls.from_pretrained.call_count == 1
