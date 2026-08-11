"""Phase 6 — Qdrant vector database service.

Thin wrapper around ``qdrant-client`` providing collection management, batched
upserts, similarity search and per-document vector deletion. Point payloads
carry the source metadata (document_id, chunk_id, chunk_index, filename,
document_type) so search results can be traced back to their origin.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.models import PointStruct

from app.core.config import settings

logger = logging.getLogger(__name__)


class QdrantService:
    """Client wrapper for interacting with a Qdrant instance."""

    def __init__(self, url: Optional[str] = None):
        self.url = url or settings.QDRANT_URL
        self.client = QdrantClient(url=self.url)

    def ensure_collection(self, collection_name: str, vector_size: int) -> None:
        """Create ``collection_name`` (Cosine distance) if it does not exist."""
        existing = {c.name for c in self.client.get_collections().collections}
        if collection_name in existing:
            return
        logger.info(
            "Creating Qdrant collection '%s' (size=%d, Cosine)",
            collection_name,
            vector_size,
        )
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=qmodels.VectorParams(
                size=vector_size, distance=qmodels.Distance.COSINE
            ),
        )

    def upsert_vectors(
        self, collection_name: str, points: List[PointStruct]
    ) -> None:
        """Upsert a batch of points (vectors + payloads) into a collection."""
        if not points:
            return
        self.client.upsert(collection_name=collection_name, points=points)
        logger.info(
            "Upserted %d vectors into '%s'", len(points), collection_name
        )

    def similarity_search(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int = 5,
        filter_payload: Optional[dict] = None,
    ) -> List[dict]:
        """Return the ``top_k`` most similar points with score + payload.

        ``filter_payload`` is an optional ``{field: value}`` mapping applied as
        an exact-match Qdrant filter (e.g. ``{"document_id": "..."}``).
        """
        query_filter = None
        if filter_payload:
            query_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key=key, match=qmodels.MatchValue(value=value)
                    )
                    for key, value in filter_payload.items()
                ]
            )

        hits = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )
        return [
            {"id": str(hit.id), "score": hit.score, "payload": hit.payload or {}}
            for hit in hits
        ]

    def delete_document_vectors(
        self, collection_name: str, document_id: str
    ) -> None:
        """Delete all vectors for ``document_id`` using a payload filter."""
        self.client.delete(
            collection_name=collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=str(document_id)),
                        )
                    ]
                )
            ),
        )
        logger.info(
            "Deleted vectors for document %s from '%s'",
            document_id,
            collection_name,
        )
