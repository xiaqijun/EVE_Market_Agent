import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, BigInteger, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TradeOpportunity(Base):
    __tablename__ = "trade_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(20))
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    buy_station_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    sell_station_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    buy_price: Mapped[float] = mapped_column(Float, nullable=True)
    sell_price: Mapped[float] = mapped_column(Float, nullable=True)
    estimated_profit: Mapped[float] = mapped_column(Float, nullable=True)
    estimated_profit_pct: Mapped[float] = mapped_column(Float, nullable=True)
    cost_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=True)
    volume_confidence: Mapped[float] = mapped_column(Float, default=0)
    agent_analysis: Mapped[str] = mapped_column(Text, nullable=True)
    recommendation_score: Mapped[int] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    triggered_by: Mapped[str] = mapped_column(String(20))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    analysis_completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    analysis_model: Mapped[str] = mapped_column(String(50), nullable=True)


class UserTrade(Base):
    __tablename__ = "user_trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("eve_characters.id"), nullable=True)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trade_opportunities.id"), nullable=True)
    type_id: Mapped[int] = mapped_column(Integer)
    station_id: Mapped[int] = mapped_column(Integer)
    is_buy: Mapped[bool] = mapped_column(Boolean)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    total_cost: Mapped[float] = mapped_column(Float)
    broker_fee: Mapped[float] = mapped_column(Float, default=0)
    tax: Mapped[float] = mapped_column(Float, default=0)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    esi_order_id: Mapped[int] = mapped_column(BigInteger, nullable=True, unique=True)
    esi_transaction_id: Mapped[int] = mapped_column(BigInteger, nullable=True, unique=True)


class FeedbackRecord(Base):
    __tablename__ = "feedback_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trade_opportunities.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    outcome: Mapped[str] = mapped_column(String(20))
    actual_profit: Mapped[float] = mapped_column(Float, nullable=True)
    roi_pct: Mapped[float] = mapped_column(Float, nullable=True)
    market_prices_at_exit: Mapped[dict] = mapped_column(JSONB, nullable=True)
    exit_reason: Mapped[str] = mapped_column(String(200), nullable=True)
    agent_self_review: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssetSnapshot(Base):
    __tablename__ = "asset_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("eve_characters.id"))
    snapshot_data: Mapped[dict] = mapped_column(JSONB)
    total_isk: Mapped[float] = mapped_column(Float, default=0)
    total_asset_value: Mapped[float] = mapped_column(Float, default=0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
