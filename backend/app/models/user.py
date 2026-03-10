from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    recipes = relationship("Recipe", back_populates="owner", cascade="all, delete-orphan")
    ratings = relationship("RecipeRating", back_populates="user", cascade="all, delete-orphan")
    external_ratings = relationship(
        "ExternalRecipeRating", back_populates="user", cascade="all, delete-orphan"
    )
    suggestion_cache = relationship(
        "UserSuggestionCache", back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    weekly_plans = relationship("WeeklyPlan", back_populates="user", cascade="all, delete-orphan")
