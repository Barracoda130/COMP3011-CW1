from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure tests never write to the default development database.
TEST_DB_PATH = Path(__file__).resolve().parents[1] / "test_meal_api.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"

from app.db.session import get_db  # noqa: E402
from app.db.session import engine as app_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


test_engine = create_engine(
    os.environ["DATABASE_URL"],
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def override_database_dependency() -> None:
    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_database() -> None:
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_database() -> None:
    yield
    test_engine.dispose()
    app_engine.dispose()
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except PermissionError:
            # Windows can keep sqlite handles alive briefly after test shutdown.
            pass
