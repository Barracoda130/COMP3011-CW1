from functools import lru_cache

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "Taste-Based Weekly Meal Recommendation API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    BACKEND_CORS_ORIGINS: list[AnyHttpUrl | str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    DATABASE_URL: str = "sqlite:///./meal_api.db"
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    THEMEALDB_BASE_URL: str = "https://www.themealdb.com/api/json/v1/1"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
