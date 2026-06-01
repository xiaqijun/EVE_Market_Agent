"""add analysis fields to trade_opportunities

Revision ID: 005
Revises: 004_remove_station_fk
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004_remove_station_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trade_opportunities", sa.Column("analysis_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trade_opportunities", sa.Column("analysis_model", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("trade_opportunities", "analysis_model")
    op.drop_column("trade_opportunities", "analysis_completed_at")
