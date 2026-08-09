"""Add transcript chunk vector storage.

Revision ID: 0002_vector_storage
Revises: 0001_meetings
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0002_vector_storage"
down_revision: str | None = "0001_meetings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "transcript_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "meeting_id",
            "chunk_index",
            name="uq_transcript_chunks_meeting_id_chunk_index",
        ),
    )
    op.create_index(
        op.f("ix_transcript_chunks_meeting_id"),
        "transcript_chunks",
        ["meeting_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_transcript_chunks_meeting_id"),
        table_name="transcript_chunks",
    )
    op.drop_table("transcript_chunks")
