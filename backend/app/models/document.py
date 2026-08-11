from sqlalchemy import (
    Column,
    String,
    Enum,
    DateTime,
    Integer,
    Text,
    Boolean,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid, enum
from app.db.session import Base


class DocumentType(str, enum.Enum):
    PDF = "PDF"
    DOCX = "DOCX"
    TXT = "TXT"
    HTML = "HTML"


class DocumentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    owner_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    file_size = Column(Integer, nullable=False)
    status = Column(
        Enum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False
    )
    page_count = Column(Integer, nullable=True)
    raw_text = Column(Text, nullable=True)
    error_message = Column(String, nullable=True)
    # Soft-delete flag (DELETE endpoint marks this instead of hard-removing).
    is_deleted = Column(Boolean, default=False, nullable=False)

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
