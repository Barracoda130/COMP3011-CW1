from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UserSuggestionCache(Base):
    __tablename__ = "user_suggestion_cache"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_suggestion_cache"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    items_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    user = relationship("User", back_populates="suggestion_cache")
