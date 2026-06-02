from sqlalchemy import String, Integer, BigInteger, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SdeCategory(Base):
    __tablename__ = "sde_categories"
    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))


class SdeRegion(Base):
    __tablename__ = "sde_regions"
    region_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000), nullable=True)


class SdeSystem(Base):
    __tablename__ = "sde_systems"
    system_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    region_id: Mapped[int] = mapped_column(Integer, ForeignKey("sde_regions.region_id"))
    security_status: Mapped[float] = mapped_column(Float)


class SdeStation(Base):
    __tablename__ = "sde_stations"
    station_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    name_zh: Mapped[str] = mapped_column(String(200), nullable=True)
    system_id: Mapped[int] = mapped_column(Integer, index=True)
    station_type: Mapped[str] = mapped_column(String(50))


class SdeItemGroup(Base):
    __tablename__ = "sde_item_groups"
    group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("sde_categories.category_id"), nullable=True)


class SdeItem(Base):
    __tablename__ = "sde_items"
    type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("sde_item_groups.group_id"))
    volume: Mapped[float] = mapped_column(Float, default=0.01)
    base_price: Mapped[float] = mapped_column(Float, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
