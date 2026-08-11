"""Phase 3 & 4 — Document ingestion + chunk retrieval API.

Endpoints (mounted at ``/api/v1/documents``):
    POST   /upload              upload a file, create record, trigger processing
    GET    /                    list current user's documents (paginated)
    GET    /{doc_id}            get a single document's details
    DELETE /{doc_id}            soft-delete (ADMIN or owner only)
    GET    /{doc_id}/status     processing status
    GET    /{doc_id}/chunks     list chunks for a document (ADMIN or owner)
"""
import os
import uuid
import logging

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    HTTPException,
    status,
    Query,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.core.security import get_current_user
from app.models.document import Document, DocumentType, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.user import UserRole
from app.schemas.document import (
    DocumentOut,
    DocumentDetail,
    DocumentStatusOut,
    DocumentList,
    ChunkOut,
    ChunkList,
)
from app.services.document_service import process_document

logger = logging.getLogger(__name__)

router = APIRouter()

# Map file extensions to their DocumentType.
_EXT_TO_TYPE = {
    ".pdf": DocumentType.PDF,
    ".docx": DocumentType.DOCX,
    ".txt": DocumentType.TXT,
    ".html": DocumentType.HTML,
    ".htm": DocumentType.HTML,
}


def _resolve_document_type(filename: str) -> DocumentType:
    ext = os.path.splitext(filename)[1].lower()
    doc_type = _EXT_TO_TYPE.get(ext)
    if doc_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported file type. Allowed: "
                "PDF, DOCX, TXT, HTML"
            ),
        )
    return doc_type


def _get_owned_document(
    doc_id: uuid.UUID, db: Session, user: dict, include_deleted: bool = False
) -> Document:
    """Fetch a document enforcing owner/ADMIN access control."""
    query = db.query(Document).filter(Document.id == doc_id)
    if not include_deleted:
        query = query.filter(Document.is_deleted.is_(False))
    document = query.first()
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


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Upload a document, persist it to disk, create a DB record and run the
    extraction + chunking pipeline synchronously."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    doc_type = _resolve_document_type(file.filename)

    # Read the file, enforcing the max size limit.
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE} bytes",
        )

    # Ensure the upload directory exists.
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Store under a unique, safe filename to avoid collisions/traversal.
    ext = os.path.splitext(file.filename)[1].lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, stored_name)
    with open(file_path, "wb") as out:
        out.write(contents)

    document = Document(
        filename=stored_name,
        original_filename=file.filename,
        file_path=file_path,
        document_type=doc_type,
        owner_id=uuid.UUID(str(user["id"])),
        file_size=len(contents),
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Trigger the extraction + chunking pipeline.
    document = process_document(document.id, db)
    return document


@router.get("/", response_model=DocumentList)
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List the current user's (non-deleted) documents, paginated."""
    base = db.query(Document).filter(
        Document.owner_id == uuid.UUID(str(user["id"])),
        Document.is_deleted.is_(False),
    )
    total = base.count()
    items = (
        base.order_by(Document.upload_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return DocumentList(
        total=total, page=page, page_size=page_size, items=items
    )


@router.get("/{doc_id}", response_model=DocumentDetail)
def get_document(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get a single document's details (owner or ADMIN)."""
    return _get_owned_document(doc_id, db, user)


@router.get("/{doc_id}/status", response_model=DocumentStatusOut)
def get_document_status(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get the processing status of a document (owner or ADMIN)."""
    return _get_owned_document(doc_id, db, user)


@router.get("/{doc_id}/chunks", response_model=ChunkList)
def get_document_chunks(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List all chunks generated for a document (owner or ADMIN)."""
    document = _get_owned_document(doc_id, db, user)
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )
    return ChunkList(total=len(chunks), items=chunks)


@router.delete("/{doc_id}", status_code=200)
def delete_document(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Soft-delete a document (ADMIN or owner only)."""
    document = _get_owned_document(doc_id, db, user)
    document.is_deleted = True
    db.commit()
    return {"message": "Document deleted", "id": str(doc_id)}
