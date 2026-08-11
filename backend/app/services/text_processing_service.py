"""Phase 4 — Text Processing (cleaning + chunking).

Cleans extracted document text and splits it into overlapping, token-aware
chunks using LangChain's RecursiveCharacterTextSplitter with the tiktoken
``cl100k_base`` encoding. Chunks are persisted to the ``document_chunks`` table.
"""
import re
import logging

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

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
    return len(chunks)
