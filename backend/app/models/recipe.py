from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(150), index=True)
    cuisine: Mapped[str] = mapped_column(String(60), index=True)
    prep_minutes: Mapped[int] = mapped_column(Integer)
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protein_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbs_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    allergens: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingredients: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    average_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    owner = relationship("User", back_populates="recipes")
    ratings = relationship("RecipeRating", back_populates="recipe", cascade="all, delete-orphan")
    weekly_plan_items = relationship("WeeklyPlanItem", back_populates="recipe")
