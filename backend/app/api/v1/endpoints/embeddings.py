"""Phase 5 & 6 — Embedding + semantic search API.

Endpoints (mounted at ``/api/v1/embeddings``):
    POST /embeddings/{doc_id}/generate   trigger embedding generation (ADMIN/owner)
    GET  /embeddings/{doc_id}/status     embedded-vs-total chunk counts
    POST /search                         semantic similarity search
"""
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.embedding_metadata import EmbeddingMetadata
from app.models.user import UserRole
from app.schemas.embedding import (
    EmbeddingGenerateOut,
    EmbeddingStatusOut,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services.embedding_service import EmbeddingFactory
from app.services.text_processing_service import index_document_embeddings
from app.services.vector_service import QdrantService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_owned_document(doc_id: uuid.UUID, db: Session, user: dict) -> Document:
    """Fetch a non-deleted document enforcing owner/ADMIN access."""
    document = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.is_deleted.is_(False))
        .first()
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    is_owner = str(document.owner_id) == str(user["id"])
    is_admin = user["role"] == UserRole.ADMIN.value
    if not (is_owner or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this document",
        )
    return document


@router.post("/{doc_id}/generate", response_model=EmbeddingGenerateOut)
def generate_embeddings(
    doc_id: uuid.UUID,
    embedding_model: str = settings.DEFAULT_EMBEDDING_MODEL,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """(Re)generate embeddings for a document and index them in Qdrant."""
    document = _get_owned_document(doc_id, db, user)
    try:
        indexed = index_document_embeddings(
            document.id, db, provider_name=embedding_model
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Embedding generation failed for %s", doc_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation failed: {exc}",
        )
    return EmbeddingGenerateOut(
        document_id=str(document.id),
        indexed_chunks=indexed,
        embedding_model=embedding_model,
        message=(
            f"Indexed {indexed} chunk embedding(s) for document {document.id}"
        ),
    )


@router.get("/{doc_id}/status", response_model=EmbeddingStatusOut)
def embedding_status(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Report how many of a document's chunks are embedded vs the total."""
    document = _get_owned_document(doc_id, db, user)
    total = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .count()
    )
    embedded = (
        db.query(EmbeddingMetadata)
        .filter(EmbeddingMetadata.document_id == document.id)
        .count()
    )
    model_row = (
        db.query(EmbeddingMetadata.embedding_model)
        .filter(EmbeddingMetadata.document_id == document.id)
        .first()
    )
    return EmbeddingStatusOut(
        document_id=str(document.id),
        total_chunks=total,
        embedded_chunks=embedded,
        embedding_model=model_row[0] if model_row else None,
        fully_embedded=total > 0 and embedded >= total,
    )


@router.post("/search", response_model=SearchResponse)
def semantic_search(
    body: SearchRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Embed the query and return the top_k most similar chunks from Qdrant."""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty")

    try:
        provider = EmbeddingFactory.get_provider(body.embedding_model)
        query_vector = provider.embed([body.query])[0]
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to embed search query")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to embed query: {exc}",
        )

    try:
        qdrant = QdrantService()
        hits = qdrant.similarity_search(
            settings.QDRANT_COLLECTION, query_vector, top_k=body.top_k
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Vector search failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector search failed: {exc}",
        )

    # Enrich results with the chunk text from the database.
    results = []
    for hit in hits:
        payload = hit.get("payload", {})
        chunk_id = payload.get("chunk_id")
        content = None
        if chunk_id:
            chunk = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.id == uuid.UUID(chunk_id))
                .first()
            )
            content = chunk.content if chunk else None
        results.append(
            SearchResult(
                score=hit.get("score"),
                content=content,
                document_id=payload.get("document_id"),
                chunk_id=chunk_id,
                chunk_index=payload.get("chunk_index"),
                filename=payload.get("filename"),
                document_type=payload.get("document_type"),
            )
        )

    return SearchResponse(
        query=body.query,
        top_k=body.top_k,
        embedding_model=body.embedding_model,
        results=results,
    )
