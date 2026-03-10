from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    user = relationship("User", back_populates="weekly_plans")
    items = relationship("WeeklyPlanItem", back_populates="weekly_plan", cascade="all, delete-orphan")


class WeeklyPlanItem(Base):
    __tablename__ = "weekly_plan_items"
    __table_args__ = (
        UniqueConstraint("weekly_plan_id", "day_index", "recipe_source", name="uq_weekly_plan_day_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    weekly_plan_id: Mapped[int] = mapped_column(ForeignKey("weekly_plans.id", ondelete="CASCADE"), index=True)
    day_index: Mapped[int] = mapped_column(Integer, index=True)
    planned_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    recipe_source: Mapped[str] = mapped_column(String(20), default="local")
    recipe_id: Mapped[int | None] = mapped_column(ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True)
    external_recipe_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title_snapshot: Mapped[str] = mapped_column(String(150))
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    weekly_plan = relationship("WeeklyPlan", back_populates="items")
    recipe = relationship("Recipe", back_populates="weekly_plan_items")
