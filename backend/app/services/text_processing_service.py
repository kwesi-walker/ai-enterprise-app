"""Phase 4 — Text Processing (cleaning + chunking).

Cleans extracted document text and splits it into overlapping, token-aware
chunks using LangChain's RecursiveCharacterTextSplitter with the tiktoken
``cl100k_base`` encoding. Chunks are persisted to the ``document_chunks`` table.
"""
import re
import logging
from datetime import datetime, timezone

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)

# Shared tiktoken encoder (cl100k_base is used by GPT-3.5/4 & most embeddings).
_ENCODING = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def clean_text(text: str) -> str:
    """Normalise raw extracted text.

    - Normalises line endings.
    - Strips common page-header/footer noise such as ``Page 3 of 10``.
    - Collapses excessive whitespace and blank lines.
    - Removes non-printable/control characters.
    """
    if not text:
        return ""

    # Normalise line endings.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove obvious page-number / header-footer patterns on their own lines.
    page_patterns = [
        r"(?im)^\s*page\s+\d+\s*(of\s+\d+)?\s*$",
        r"(?m)^\s*[-–—]?\s*\d+\s*[-–—]?\s*$",  # standalone page numbers
    ]
    for pattern in page_patterns:
        text = re.sub(pattern, "", text)

    # Remove control / non-printable characters (keep newlines and tabs).
    text = re.sub(r"[^\x09\x0A\x20-\x7E\u00A0-\uFFFF]", "", text)

    # Collapse runs of spaces/tabs.
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Collapse 3+ newlines down to a paragraph break.
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip trailing spaces on each line.
    text = re.sub(r"[ \t]+\n", "\n", text)

    return text.strip()


def chunk_document(text: str, chunk_size: int = 1000, chunk_overlap: int = 200):
    """Split ``text`` into token-aware chunks with character offsets.

    Uses ``RecursiveCharacterTextSplitter`` configured with a tiktoken length
    function so ``chunk_size`` / ``chunk_overlap`` are measured in tokens
    (cl100k_base). Returns a list of dicts with content, token_count and the
    character start/end offsets within the (cleaned) source text.
    """
    if not text:
        return []

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    pieces = splitter.split_text(text)

    chunks = []
    search_from = 0
    for index, piece in enumerate(pieces):
        # Locate the chunk within the source text to record char offsets.
        char_start = text.find(piece, search_from)
        if char_start == -1:
            # Fallback: search from the beginning if overlap moved the cursor.
            char_start = text.find(piece)
        if char_start == -1:
            char_start = search_from
        char_end = char_start + len(piece)
        # Advance the search cursor accounting for overlap between chunks.
        search_from = max(char_start + 1, char_end - 1)

        chunks.append(
            {
                "chunk_index": index,
                "content": piece,
                "token_count": _count_tokens(piece),
                "char_start": char_start,
                "char_end": char_end,
            }
        )

    return chunks


def process_chunks(document_id, db: Session) -> int:
    """Clean the document's raw text, chunk it and persist the chunks.

    Returns the number of chunks created. Any existing chunks for the document
    are removed first so the operation is idempotent.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise ValueError(f"Document {document_id} not found")

    if not document.raw_text:
        logger.warning("Document %s has no raw_text to chunk", document_id)
        return 0

    # Remove any previously generated chunks (idempotent re-processing).
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document.id
    ).delete(synchronize_session=False)

    cleaned = clean_text(document.raw_text)
    chunks = chunk_document(cleaned)

    for chunk in chunks:
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=chunk["chunk_index"],
                content=chunk["content"],
                token_count=chunk["token_count"],
                char_start=chunk["char_start"],
                char_end=chunk["char_end"],
            )
        )

    db.commit()
    logger.info("Created %d chunks for document %s", len(chunks), document_id)

    # Phase 5 & 6: automatically embed the chunks and index them in Qdrant.
    try:
        index_document_embeddings(document.id, db)
    except Exception as exc:  # noqa: BLE001 — indexing must not fail chunking
        logger.exception(
            "Embedding/indexing failed for document %s: %s", document_id, exc
        )

    return len(chunks)


def index_document_embeddings(
    document_id, db: Session, provider_name: str | None = None
) -> int:
    """Generate embeddings for a document's chunks and upsert them to Qdrant.

    For each chunk this: (1) generates a vector via the configured embedding
    provider, (2) upserts the vector + source payload into the Qdrant
    collection, and (3) records an ``EmbeddingMetadata`` row (idempotent —
    existing rows/vectors for the document are removed first). Returns the
    number of vectors indexed.
    """
    # Imported here to avoid heavy imports at module load / circular imports.
    from qdrant_client.http.models import PointStruct

    from app.models.embedding_metadata import EmbeddingMetadata
    from app.services.embedding_service import generate_embeddings_for_document
    from app.services.vector_service import QdrantService

    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise ValueError(f"Document {document_id} not found")

    provider_name = provider_name or settings.DEFAULT_EMBEDDING_MODEL
    collection = settings.QDRANT_COLLECTION

    results, provider = generate_embeddings_for_document(
        document_id, provider_name, db
    )
    if not results:
        logger.warning("No embeddings generated for document %s", document_id)
        return 0

    dimension = provider.dimension or len(results[0][1])

    qdrant = QdrantService()
    qdrant.ensure_collection(collection, dimension)
    # Idempotent re-indexing: clear prior vectors/metadata for this document.
    qdrant.delete_document_vectors(collection, str(document.id))
    db.query(EmbeddingMetadata).filter(
        EmbeddingMetadata.document_id == document.id
    ).delete(synchronize_session=False)

    # Look up chunk_index per chunk for payloads.
    chunk_index_by_id = {
        c.id: c.chunk_index
        for c in db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .all()
    }

    points = []
    now = datetime.now(timezone.utc)
    for chunk_id, vector, point_id in results:
        payload = {
            "document_id": str(document.id),
            "chunk_id": str(chunk_id),
            "chunk_index": chunk_index_by_id.get(chunk_id),
            "filename": document.original_filename,
            "document_type": document.document_type.value,
        }
        points.append(
            PointStruct(id=str(point_id), vector=vector, payload=payload)
        )
        db.add(
            EmbeddingMetadata(
                chunk_id=chunk_id,
                document_id=document.id,
                embedding_model=provider.model_name,
                embedding_dimension=dimension,
                qdrant_point_id=point_id,
                indexed_at=now,
            )
        )

    qdrant.upsert_vectors(collection, points)
    db.commit()
    logger.info(
        "Indexed %d vectors for document %s in collection '%s'",
        len(points),
        document_id,
        collection,
    )
    return len(points)
