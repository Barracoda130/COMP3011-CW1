from sqlalchemy import text

from app.db.session import engine
from app.models import Base  # noqa: F401


def init_db() -> None:
    # Keep startup table creation for local/test convenience.
    # Incremental schema changes are managed through Alembic migrations.
    Base.metadata.create_all(bind=engine)

    # Align legacy SQLite dev/test databases with current weekly plan schema.
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as connection:
        tables = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        table_names = {row[0] for row in tables}

        if "recipes" in table_names:
            recipe_columns = connection.execute(text("PRAGMA table_info('recipes')")).fetchall()
            recipe_column_names = {row[1] for row in recipe_columns}
            if "protein_g" not in recipe_column_names:
                connection.execute(text("ALTER TABLE recipes ADD COLUMN protein_g FLOAT"))
            if "carbs_g" not in recipe_column_names:
                connection.execute(text("ALTER TABLE recipes ADD COLUMN carbs_g FLOAT"))
            if "fat_g" not in recipe_column_names:
                connection.execute(text("ALTER TABLE recipes ADD COLUMN fat_g FLOAT"))
            if "allergens" not in recipe_column_names:
                connection.execute(text("ALTER TABLE recipes ADD COLUMN allergens JSON"))
            if "cost_estimate" not in recipe_column_names:
                connection.execute(text("ALTER TABLE recipes ADD COLUMN cost_estimate FLOAT"))

        if "weekly_plan_items" not in table_names:
            return

        columns = connection.execute(text("PRAGMA table_info('weekly_plan_items')")).fetchall()
        column_names = {row[1] for row in columns}

        index_rows = connection.execute(text("PRAGMA index_list('weekly_plan_items')")).fetchall()
        has_old_unique = False
        has_new_unique = False
        for index_row in index_rows:
            index_name = index_row[1]
            is_unique = bool(index_row[2])
            if not is_unique:
                continue
            indexed_columns = connection.execute(text(f"PRAGMA index_info('{index_name}')")).fetchall()
            indexed_names = [item[2] for item in indexed_columns]
            if indexed_names == ["weekly_plan_id", "day_index"]:
                has_old_unique = True
            if indexed_names == ["weekly_plan_id", "day_index", "recipe_source"]:
                has_new_unique = True

        if "is_selected" in column_names and has_new_unique and not has_old_unique:
            return

        connection.execute(text("ALTER TABLE weekly_plan_items RENAME TO weekly_plan_items_old"))
        connection.execute(
            text(
                """
                CREATE TABLE weekly_plan_items (
                  id INTEGER NOT NULL PRIMARY KEY,
                  weekly_plan_id INTEGER NOT NULL,
                  day_index INTEGER NOT NULL,
                  planned_for DATE NULL,
                  recipe_source VARCHAR(20) NOT NULL DEFAULT 'local',
                  recipe_id INTEGER NULL,
                  external_recipe_id VARCHAR(64) NULL,
                  title_snapshot VARCHAR(150) NOT NULL,
                  is_selected BOOLEAN NOT NULL DEFAULT 0,
                  notes TEXT NULL,
                  created_at DATETIME NOT NULL,
                  FOREIGN KEY(weekly_plan_id) REFERENCES weekly_plans (id) ON DELETE CASCADE,
                  FOREIGN KEY(recipe_id) REFERENCES recipes (id) ON DELETE SET NULL,
                  CONSTRAINT uq_weekly_plan_day_source UNIQUE (weekly_plan_id, day_index, recipe_source)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO weekly_plan_items (
                  id,
                  weekly_plan_id,
                  day_index,
                  planned_for,
                  recipe_source,
                  recipe_id,
                  external_recipe_id,
                  title_snapshot,
                  is_selected,
                  notes,
                  created_at
                )
                SELECT
                  id,
                  weekly_plan_id,
                  day_index,
                  planned_for,
                  recipe_source,
                  recipe_id,
                  external_recipe_id,
                  title_snapshot,
                  0,
                  notes,
                  created_at
                FROM weekly_plan_items_old
                """
            )
        )
        connection.execute(text("DROP TABLE weekly_plan_items_old"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_weekly_plan_items_id ON weekly_plan_items (id)"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_weekly_plan_items_weekly_plan_id ON weekly_plan_items (weekly_plan_id)")
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_weekly_plan_items_day_index ON weekly_plan_items (day_index)")
        )
