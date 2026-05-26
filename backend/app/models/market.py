from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, BigInteger, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MarketOrder(Base):
    __tablename__ = "market_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(Integer, index=True)
    station_id: Mapped[int] = mapped_column(Integer)
    region_id: Mapped[int] = mapped_column(Integer, index=True)
    system_id: Mapped[int] = mapped_column(Integer)
    order_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    is_buy_order: Mapped[bool] = mapped_column(Boolean)
    price: Mapped[float] = mapped_column(Float)
    volume_remain: Mapped[int] = mapped_column(Integer)
    volume_total: Mapped[int] = mapped_column(Integer)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration: Mapped[int] = mapped_column(Integer)
    range: Mapped[str] = mapped_column(String(50))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class MarketHistory(Base):
    __tablename__ = "market_history"
    __table_args__ = (
        UniqueConstraint("type_id", "region_id", "date", name="uq_market_history"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(Integer)
    region_id: Mapped[int] = mapped_column(Integer)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lowest: Mapped[float] = mapped_column(Float)
    average: Mapped[float] = mapped_column(Float)
    highest: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)
    order_count: Mapped[int] = mapped_column(Integer)
