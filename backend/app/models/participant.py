import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ParticipantSession(Base):
    __tablename__ = "participant_sessions"
    __table_args__ = (
        UniqueConstraint("room_id", "slot", name="uq_room_slot"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("rooms.id"), nullable=False, index=True)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 or 2
    session_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    is_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
