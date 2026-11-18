from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.bootstrap import ensure_superuser
from app.core.config import get_settings
from app.core.security import verify_password
from app.users.models import User
from app.users.service import get_user_by_email


def test_ensure_superuser_creates_account(db: Session) -> None:
    settings = get_settings()
    ensure_superuser(db)

    user = get_user_by_email(db, settings.superuser_email)
    assert user is not None
    assert user.is_superuser
    assert user.is_active
    assert verify_password(settings.superuser_password.get_secret_value(), user.password_hash)


def test_ensure_superuser_is_idempotent_and_keeps_password(db: Session) -> None:
    ensure_superuser(db)
    user = get_user_by_email(db, get_settings().superuser_email)
    assert user is not None
    original_hash = user.password_hash
    user.is_superuser = False
    db.commit()

    ensure_superuser(db)
    db.refresh(user)
    assert user.is_superuser  # flag restored
    assert user.password_hash == original_hash  # password untouched
    assert db.query(User).count() == 1


def test_tools_listing(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    assert client.get("/api/tools").status_code == 401

    make_user("someone@example.com")
    login("someone@example.com")
    tools = client.get("/api/tools").json()
    assert {t["id"] for t in tools} == {"github", "linear"}

    r = client.get("/api/tools/github/status")
    assert r.status_code == 200
    assert "configured" in r.json()
