from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Float, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from app.models.base import Base


class MoodflowChatMessage(Base):
    __tablename__ = "moodflow_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('user','assistant','system')", name="moodflow_chat_messages_role_ck"),
        Index("moodflow_chat_messages_user_ts_idx", "user_id", "ts"),
    )


class MoodflowUserProfile(Base):
    __tablename__ = "moodflow_user_profiles"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MoodflowUserMemory(Base):
    __tablename__ = "moodflow_user_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # The embedding column is managed via raw SQL in the store to avoid pgvector SQLAlchemy coupling.
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    text_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
