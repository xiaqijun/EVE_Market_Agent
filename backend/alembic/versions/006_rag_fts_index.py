"""add full-text search index on rag_documents

Revision ID: 006
Revises: 005
Create Date: 2026-06-02
"""
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_rag_doc_fts
        ON rag_documents
        USING gin(to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, '')))
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_rag_doc_fts")
