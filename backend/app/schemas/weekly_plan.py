from datetime import date, datetime

from pydantic import BaseModel, Field


class WeeklyPlanItemRead(BaseModel):
    id: int
    day_index: int
    planned_for: date | None = None
    recipe_source: str
    recipe_id: int | None = None
    external_recipe_id: str | None = None
    title_snapshot: str
    is_selected: bool
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WeeklyPlanRead(BaseModel):
    id: int
    user_id: int
    start_date: date
    end_date: date
    status: str
    created_at: datetime
    items: list[WeeklyPlanItemRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class WeeklyPlanSelectionUpdate(BaseModel):
    day_index: int = Field(ge=0, le=6)
    recipe_source: str
