import secrets
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def generate_slug() -> str:
    return secrets.token_urlsafe(8)  # ~11 URL-safe chars


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    url: Mapped[str] = mapped_column(String(500))
    video_id: Mapped[str] = mapped_column(String(50), index=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True, default=generate_slug)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    language: Mapped[str] = mapped_column(String(20), default="French")
    caveman: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
