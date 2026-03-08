from pydantic import BaseModel, Field


class RatingCreate(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class RatingRead(BaseModel):
    id: int
    user_id: int
    recipe_id: int
    score: int
    comment: str | None = None

    model_config = {"from_attributes": True}


class ExternalRatingRead(BaseModel):
    id: int
    user_id: int
    external_recipe_id: str
    source: str
    score: int
    comment: str | None = None

    model_config = {"from_attributes": True}
