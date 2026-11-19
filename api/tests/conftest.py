"""Shared test fixtures.

Tests run against a separate database (``<POSTGRES_DB>_test``) so they never
touch development data. The schema is built once per test run by applying the
real Alembic migrations, which also checks that the migrations work. Every
table is emptied before each test so tests cannot affect each other.
"""

import os

# Point the app at the test database. This must happen BEFORE any `app.*`
# import, because the database engine is created when app.core.db is imported.
_base_db = os.environ.get("POSTGRES_DB", "coursemgmt")
os.environ["POSTGRES_DB"] = os.environ.get("TEST_POSTGRES_DB", f"{_base_db}_test")
os.environ["ENVIRONMENT"] = "test"

from collections.abc import Callable, Iterator  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.users.models import User  # noqa: E402
from app.users.service import create_user  # noqa: E402

PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session", autouse=True)
def _database_schema() -> Iterator[None]:
    """Rebuild the test database schema from the migrations, once per run."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(Config("alembic.ini"), "head")
    yield


@pytest.fixture(autouse=True)
def _clean_tables() -> None:
    """Empty every table before each test."""
    table_names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    """Factory: ``make_user("a@example.com", is_superuser=True)``."""

    def _make(email: str = "user@example.com", **kwargs: object) -> User:
        return create_user(db, email=email, password=PASSWORD, **kwargs)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def login(client: TestClient) -> Callable[[str], None]:
    """Log ``client`` in as the given email (password is ``PASSWORD``)."""

    def _login(email: str) -> None:
        r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text

    return _login
