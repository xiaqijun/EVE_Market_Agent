"""change EVE IDs from int32 to int64 (BigInteger)

Revision ID: 007
Revises: 006
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # sde_stations.station_id: Integer → BigInteger
    op.alter_column("sde_stations", "station_id", type_=sa.BigInteger())

    # eve_characters: character_id, corporation_id, alliance_id
    op.alter_column("eve_characters", "character_id", type_=sa.BigInteger())
    op.alter_column("eve_characters", "corporation_id", type_=sa.BigInteger())
    op.alter_column("eve_characters", "alliance_id", type_=sa.BigInteger())

    # user_trades.station_id
    op.alter_column("user_trades", "station_id", type_=sa.BigInteger())


def downgrade() -> None:
    op.alter_column("user_trades", "station_id", type_=sa.Integer())
    op.alter_column("eve_characters", "alliance_id", type_=sa.Integer())
    op.alter_column("eve_characters", "corporation_id", type_=sa.Integer())
    op.alter_column("eve_characters", "character_id", type_=sa.Integer())
    op.alter_column("sde_stations", "station_id", type_=sa.Integer())
