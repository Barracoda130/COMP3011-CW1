from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ExternalRecipeRating(Base):
    __tablename__ = "external_recipe_ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "external_recipe_id", name="uq_user_external_recipe_rating"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    external_recipe_id: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(40), default="themealdb")
    score: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    user = relationship("User", back_populates="external_ratings")
