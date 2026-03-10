from app.db.session import engine
from app.models import Base  # noqa: F401


def init_db() -> None:
    # Keep startup table creation for local/test convenience.
    # Incremental schema changes are managed through Alembic migrations.
    Base.metadata.create_all(bind=engine)
