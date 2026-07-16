"""Embedding generation via Vertex AI text-embedding models."""

import logging
from typing import Any

from google.cloud import aiplatform

from .config import PipelineConfig

logger = logging.getLogger(__name__)


class Embedder:
    """Generates vector embeddings for text chunks using Vertex AI."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        aiplatform.init(project=config.project_id, location=config.embedding_location)
        self._model = None

    @property
    def model(self) -> Any:
        if self._model is None:
            from vertexai.language_models import TextEmbeddingModel

            self._model = TextEmbeddingModel.from_pretrained(
                self.config.embedding_model_name
            )
        return self._model

    def embed(self, text: str) -> list[float]:
        """Embed a single text string and return the vector."""
        embeddings = self.model.get_embeddings([text])
        return embeddings[0].values  # type: ignore[return-value]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts in one API call."""
        embeddings = self.model.get_embeddings(texts)
        return [e.values for e in embeddings]  # type: ignore[misc]
