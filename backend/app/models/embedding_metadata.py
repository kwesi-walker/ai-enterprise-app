"""Phase 5 — Embedding metadata model.

Tracks, per document chunk, which embedding model produced the vector, its
dimensionality and the point id used to store it in the Qdrant vector database.
There is exactly one embedding record per chunk (``chunk_id`` is unique).
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class EmbeddingMetadata(Base):
    __tablename__ = "embedding_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # One embedding record per chunk (unique FK).
    chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    embedding_model = Column(String, nullable=False)
    embedding_dimension = Column(Integer, nullable=False)
    # The point id used to store the vector in Qdrant.
    qdrant_point_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Set when the vector is actually pushed/indexed into Qdrant.
    indexed_at = Column(DateTime(timezone=True), nullable=True)

    chunk = relationship("DocumentChunk")
    document = relationship("Document")
