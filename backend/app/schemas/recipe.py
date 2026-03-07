from pydantic import BaseModel, Field


class RecipeBase(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    cuisine: str = Field(min_length=1, max_length=60)
    prep_minutes: int = Field(ge=1, le=600)
    calories: int | None = Field(default=None, ge=0)
    tags: list[str] = Field(default_factory=list)
    description: str | None = Field(default=None, max_length=2000)


class RecipeCreate(RecipeBase):
    pass


class RecipeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    cuisine: str | None = Field(default=None, min_length=1, max_length=60)
    prep_minutes: int | None = Field(default=None, ge=1, le=600)
    calories: int | None = Field(default=None, ge=0)
    tags: list[str] | None = None


class RecipeRead(RecipeBase):
    id: int
    owner_id: int
    average_rating: float | None = None

    model_config = {"from_attributes": True}
