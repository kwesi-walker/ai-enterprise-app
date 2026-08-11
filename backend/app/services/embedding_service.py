"""Phase 5 — Embedding generation service.

Provides a pluggable embedding provider abstraction with implementations for:

* ``SentenceTransformerProvider`` — local sentence-transformers models
  (e.g. ``all-MiniLM-L6-v2`` or ``BAAI/bge-small-en-v1.5``).
* ``OpenAIEmbeddingProvider`` — OpenAI's ``text-embedding-3-small`` (only
  usable when ``OPENAI_API_KEY`` is set).

``EmbeddingFactory.get_provider(name)`` resolves a friendly name ("minilm",
"bge", "openai") to a concrete provider. ``generate_embeddings_for_document``
fetches a document's chunks, embeds them in batches and returns
``(chunk_id, vector, qdrant_point_id)`` tuples ready to be upserted to Qdrant.
"""
from __future__ import annotations

import os
import uuid
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)

# Friendly provider name -> underlying model identifier.
_MODEL_ALIASES = {
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",
    "bge": "BAAI/bge-small-en-v1.5",
    "openai": "text-embedding-3-small",
}


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    #: Human/model identifier for this provider (recorded in metadata).
    model_name: str
    #: Dimensionality of the produced vectors (populated lazily if unknown).
    dimension: int | None = None

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return one embedding vector per input text."""
        raise NotImplementedError


class SentenceTransformerProvider(EmbeddingProvider):
    """Local embedding provider backed by ``sentence-transformers``."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None  # lazy-loaded on first use

    def _ensure_model(self):
        if self._model is None:
            # Imported lazily so the dependency is only required when used.
            from sentence_transformers import SentenceTransformer

            logger.info("Loading sentence-transformers model '%s'", self.model_name)
            self._model = SentenceTransformer(self.model_name)
            self.dimension = self._model.get_sentence_embedding_dimension()
        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._ensure_model()
        vectors = model.encode(
            texts, convert_to_numpy=True, show_progress_bar=False
        )
        return [vec.tolist() for vec in vectors]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by the OpenAI embeddings API.

    Only usable when ``OPENAI_API_KEY`` is present in the environment.
    """

    _DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, model_name: str = "text-embedding-3-small"):
        self.model_name = model_name
        self.dimension = self._DIMENSIONS.get(model_name)
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is not set; the OpenAI embedding "
                    "provider is unavailable."
                )
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)
        return self._client

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        client = self._ensure_client()
        response = client.embeddings.create(model=self.model_name, input=texts)
        # Preserve input ordering.
        data = sorted(response.data, key=lambda d: d.index)
        vectors = [item.embedding for item in data]
        if vectors and self.dimension is None:
            self.dimension = len(vectors[0])
        return vectors


class EmbeddingFactory:
    """Resolve a friendly provider name to a concrete provider instance."""

    @staticmethod
    def get_provider(name: str | None = None) -> EmbeddingProvider:
        key = (name or "minilm").lower()
        model = _MODEL_ALIASES.get(key)

        if key == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError(
                    "OpenAI embedding provider requested but OPENAI_API_KEY "
                    "is not set."
                )
            return OpenAIEmbeddingProvider(model_name=model or "text-embedding-3-small")

        if key in ("minilm", "bge"):
            return SentenceTransformerProvider(model_name=model)

        # Unknown alias: treat the raw value as a sentence-transformers model id.
        return SentenceTransformerProvider(model_name=name or "all-MiniLM-L6-v2")


def generate_embeddings_for_document(
    document_id,
    provider_name: str,
    db: Session,
    batch_size: int = 32,
) -> Tuple[List[Tuple], EmbeddingProvider]:
    """Generate embeddings for every chunk of a document.

    Fetches the document's chunks (ordered by ``chunk_index``), embeds them in
    batches of ``batch_size`` and returns a tuple ``(results, provider)`` where
    ``results`` is a list of ``(chunk_id, vector, qdrant_point_id)`` tuples and
    ``provider`` is the resolved :class:`EmbeddingProvider` (so callers can read
    ``provider.model_name`` / ``provider.dimension``).
    """
    provider = EmbeddingFactory.get_provider(provider_name)

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )
    if not chunks:
        logger.warning("No chunks found for document %s", document_id)
        return [], provider

    results: List[Tuple] = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        texts = [c.content for c in batch]
        vectors = provider.embed(texts)
        for chunk, vector in zip(batch, vectors):
            results.append((chunk.id, vector, uuid.uuid4()))

    logger.info(
        "Generated %d embeddings for document %s using '%s'",
        len(results),
        document_id,
        provider.model_name,
    )
    return results, provider
