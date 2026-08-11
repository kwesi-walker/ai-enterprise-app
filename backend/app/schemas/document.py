from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.models.document import DocumentType, DocumentStatus


class DocumentOut(BaseModel):
    id: UUID
    filename: str
    original_filename: str
    document_type: DocumentType
    owner_id: UUID
    upload_date: datetime
    file_size: int
    status: DocumentStatus
    page_count: Optional[int] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentOut):
    file_path: str
    raw_text: Optional[str] = None


class DocumentStatusOut(BaseModel):
    id: UUID
    status: DocumentStatus
    page_count: Optional[int] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class DocumentList(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[DocumentOut]


class ChunkOut(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    token_count: int
    char_start: int
    char_end: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ChunkList(BaseModel):
    total: int
    items: List[ChunkOut]
