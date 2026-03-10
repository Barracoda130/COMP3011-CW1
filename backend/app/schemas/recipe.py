from pydantic import BaseModel, Field, HttpUrl


class RecipeBase(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    cuisine: str | None = Field(default=None, max_length=60)
    prep_minutes: int = Field(ge=1, le=600)
    calories: int | None = Field(default=None, ge=0)
    intro: str | None = None
    image_url: str | None = Field(default=None, max_length=1_000_000)
    ingredients: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    steps: str | None = None


class RecipeCreate(RecipeBase):
    pass


class RecipeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    cuisine: str | None = Field(default=None, max_length=60)
    prep_minutes: int | None = Field(default=None, ge=1, le=600)
    calories: int | None = Field(default=None, ge=0)
    intro: str | None = None
    image_url: str | None = Field(default=None, max_length=1_000_000)
    ingredients: list[str] | None = None
    tags: list[str] | None = None
    steps: str | None = None


class RecipeRead(RecipeBase):
    id: int
    owner_id: int
    average_rating: float | None = None

    model_config = {"from_attributes": True}


class RecipeDiscoverItem(BaseModel):
    id: int | str
    source: str
    title: str
    cuisine: str
    image_url: str | None = None
    prep_minutes: int | None = None
    calories: int | None = None
    tags: list[str] = Field(default_factory=list)
    description: str | None = None
    average_rating: float | None = None
    owner_id: int | None = None
    external_id: str | None = None
    category: str | None = None
    key_ingredients: list[str] = Field(default_factory=list)
    recommendation_score: float | None = None


class RecipeDiscoverResponse(BaseModel):
    items: list[RecipeDiscoverItem]
    local_count: int
    external_count: int


class RecipeSuggestionResponse(BaseModel):
    items: list[RecipeDiscoverItem]
    local_count: int
    external_count: int
    formula: str


class RecipeRatedItem(RecipeDiscoverItem):
    my_rating: int
    my_comment: str | None = None


class RecipeRatedResponse(BaseModel):
    items: list[RecipeRatedItem]
    local_count: int
    external_count: int


class RecipeCookIngredient(BaseModel):
    name: str
    measure: str | None = None


class RecipeCookRead(BaseModel):
    id: int | str
    source: str
    title: str
    cuisine: str
    description: str | None = None
    instructions: str | None = None
    image_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    ingredients: list[RecipeCookIngredient] = Field(default_factory=list)
    prep_minutes: int | None = None
    calories: int | None = None


class RecipeImportRequest(BaseModel):
    url: HttpUrl


class RecipeImportPreview(BaseModel):
    title: str
    cuisine: str | None = None
    prep_minutes: int | None = None
    calories: int | None = None
    intro: str | None = None
    image_url: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    steps: str | None = None
    source_url: str
