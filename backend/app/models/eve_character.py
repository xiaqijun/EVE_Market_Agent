import uuid
from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class EveCharacter(Base):
    __tablename__ = "eve_characters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    character_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    character_name: Mapped[str] = mapped_column(String(200))
    access_token: Mapped[str] = mapped_column(String(2000))
    refresh_token: Mapped[str] = mapped_column(String(500))
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    corporation_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    alliance_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="characters")
