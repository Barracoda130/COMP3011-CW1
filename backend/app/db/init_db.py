from sqlalchemy import inspect, text

from app.db.session import engine
from app.models import Base  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    # Lightweight sqlite backfill for incremental schema changes without Alembic.
    inspector = inspect(engine)
    if "recipes" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("recipes")}
        if "intro" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE recipes ADD COLUMN intro TEXT"))

        if "steps" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE recipes ADD COLUMN steps TEXT"))

        if "description" in columns:
            with engine.begin() as connection:
                connection.execute(text("UPDATE recipes SET steps = description WHERE steps IS NULL AND description IS NOT NULL"))
                connection.execute(text("UPDATE recipes SET intro = description WHERE intro IS NULL AND description IS NOT NULL"))

        if "image_url" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE recipes ADD COLUMN image_url TEXT"))
        if "ingredients" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE recipes ADD COLUMN ingredients JSON"))

        with engine.begin() as connection:
            connection.execute(text("UPDATE recipes SET ingredients = '[]' WHERE ingredients IS NULL"))
