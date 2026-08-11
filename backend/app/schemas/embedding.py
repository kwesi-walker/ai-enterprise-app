"""Pydantic schemas for Phase 5 & 6 — embeddings + semantic search."""
from typing import List, Optional

from pydantic import BaseModel


class EmbeddingGenerateOut(BaseModel):
    """Result of triggering embedding generation for a document."""

    document_id: str
    indexed_chunks: int
    embedding_model: str
    message: str


class EmbeddingStatusOut(BaseModel):
    """How many of a document's chunks have been embedded."""

    document_id: str
    total_chunks: int
    embedded_chunks: int
    embedding_model: Optional[str] = None
    fully_embedded: bool


class SearchRequest(BaseModel):
    """Semantic search request body."""

    query: str
    top_k: int = 5
    embedding_model: str = "minilm"


class SearchResult(BaseModel):
    """A single semantic search hit."""

    score: float
    content: Optional[str] = None
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    chunk_index: Optional[int] = None
    filename: Optional[str] = None
    document_type: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    top_k: int
    embedding_model: str
    results: List[SearchResult]
