"""Set the transcript chunk embedding vector dimension.

Revision ID: 0003_embedding_dimension
Revises: 0002_vector_storage
"""
from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0003_embedding_dimension"
down_revision: str | None = "0002_vector_storage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "transcript_chunks",
        "embedding",
        existing_type=Vector(),
        type_=Vector(384),
        existing_nullable=True,
        postgresql_using="embedding::vector(384)",
    )


def downgrade() -> None:
    op.alter_column(
        "transcript_chunks",
        "embedding",
        existing_type=Vector(384),
        type_=Vector(),
        existing_nullable=True,
        postgresql_using="embedding::vector",
    )
