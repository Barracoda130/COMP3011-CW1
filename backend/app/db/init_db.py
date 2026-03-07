from app.db.session import engine
from app.models import Base  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
