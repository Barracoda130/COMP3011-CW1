from pydantic import BaseModel, Field
from datetime import date


class AnalyticsRange(BaseModel):
    min: int | None = None
    max: int | None = None
    median: int | None = None
    label: str = "insufficient-data"


class TasteProfileSummaryRead(BaseModel):
    total_ratings: int
    local_ratings: int
    external_ratings: int
    liked_ratings: int
    neutral_ratings: int
    disliked_ratings: int
    confidence: float


class TasteProfileRead(BaseModel):
    total_ratings: int
    favourite_cuisines: list[str] = Field(default_factory=list)
    favourite_tags: list[str] = Field(default_factory=list)
    favourite_ingredients: list[str] = Field(default_factory=list)
    disliked_ingredients: list[str] = Field(default_factory=list)
    preferred_prep_time_band: str = "insufficient-data"
    preferred_calorie_band: str = "insufficient-data"
    confidence: float


class PreferenceItemRead(BaseModel):
    name: str
    score: float


class PreferenceListRead(BaseModel):
    items: list[PreferenceItemRead] = Field(default_factory=list)


class WeeklyPlanDiversityRead(BaseModel):
    diversity_score: float
    total_items: int
    unique_cuisines: int
    unique_main_ingredients: int
    source_balance: float


class WeeklyNutritionSummaryRead(BaseModel):
    total_items: int
    items_with_calories: int
    total_calories: int
    average_calories: int | None = None
    min_calories: int | None = None
    max_calories: int | None = None


class RecommendationExplanationSummaryRead(BaseModel):
    total_recommendations: int
    recommendations_with_reasons: int
    top_reasons: list[PreferenceItemRead] = Field(default_factory=list)


class DistributionItemRead(BaseModel):
    name: str
    count: int
    percentage: float


class RepeatedIngredientItemRead(BaseModel):
    ingredient: str
    count: int


class QuickMealWeekdayComplianceRead(BaseModel):
    quick_threshold_minutes: int
    weekday_items: int
    items_with_prep: int
    compliant_items: int
    compliance_rate: float


class WeeklyCalorieAnalyticsRead(BaseModel):
    total_items: int
    items_with_calories: int
    total_calories: int
    average_calories: int | None = None


class WeeklyPlanAnalyticsRead(BaseModel):
    status: str
    start_date: date | None = None
    end_date: date | None = None
    total_items: int
    cuisine_distribution: list[DistributionItemRead] = Field(default_factory=list)
    repeated_ingredients: list[RepeatedIngredientItemRead] = Field(default_factory=list)
    quick_meal_weekday_compliance: QuickMealWeekdayComplianceRead
    calorie_summary: WeeklyCalorieAnalyticsRead
    diversity: WeeklyPlanDiversityRead


class AnalyticsSummaryRead(BaseModel):
    taste_profile: TasteProfileSummaryRead
    favourite_cuisines: PreferenceListRead
    favourite_ingredients: PreferenceListRead
    preferred_prep_time_range: AnalyticsRange
    preferred_calorie_range: AnalyticsRange
    weekly_plan_diversity: WeeklyPlanDiversityRead
    weekly_nutrition_summary: WeeklyNutritionSummaryRead
    recommendation_explanation_summary: RecommendationExplanationSummaryRead
