"""add embedding_metadata table (Phase 5 — embeddings)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-11 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "embedding_metadata",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("embedding_model", sa.String(), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("qdrant_point_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id"),
    )
    op.create_index(
        op.f("ix_embedding_metadata_chunk_id"),
        "embedding_metadata",
        ["chunk_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_embedding_metadata_document_id"),
        "embedding_metadata",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_embedding_metadata_document_id"),
        table_name="embedding_metadata",
    )
    op.drop_index(
        op.f("ix_embedding_metadata_chunk_id"),
        table_name="embedding_metadata",
    )
    op.drop_table("embedding_metadata")
