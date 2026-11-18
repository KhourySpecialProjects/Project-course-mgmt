from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.users.models import User
from tests.conftest import PASSWORD


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_login_sets_cookie_and_me_returns_user(
    client: TestClient, make_user: Callable[..., object]
) -> None:
    make_user("Alice@Example.com", full_name="Alice")

    # Email matching is case-insensitive.
    r = client.post("/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"
    assert "session" in r.cookies
    assert "password_hash" not in r.json()

    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["full_name"] == "Alice"


def test_login_wrong_password(client: TestClient, make_user: Callable[..., object]) -> None:
    make_user("bob@example.com")
    r = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_unknown_email(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "x"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_inactive_user_cannot_log_in(
    client: TestClient, db: Session, make_user: Callable[..., User]
) -> None:
    user = make_user("carol@example.com")
    user.is_active = False
    db.commit()

    r = client.post("/api/auth/login", json={"email": "carol@example.com", "password": PASSWORD})
    assert r.status_code == 401


def test_me_requires_login(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_logout_ends_session(
    client: TestClient, make_user: Callable[..., object], login: Callable[[str], None]
) -> None:
    make_user("dan@example.com")
    login("dan@example.com")
    assert client.get("/api/auth/me").status_code == 200

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_change_password(
    client: TestClient, make_user: Callable[..., object], login: Callable[[str], None]
) -> None:
    make_user("erin@example.com")
    login("erin@example.com")

    r = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong", "new_password": "a-new-password"},
    )
    assert r.status_code == 400

    r = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a-new-password"},
    )
    assert r.status_code == 204
    # Still logged in in this browser...
    assert client.get("/api/auth/me").status_code == 200

    # ...and the new password works for a fresh login.
    client.post("/api/auth/logout")
    r = client.post(
        "/api/auth/login", json={"email": "erin@example.com", "password": "a-new-password"}
    )
    assert r.status_code == 200


def test_new_password_must_be_long_enough(
    client: TestClient, make_user: Callable[..., object], login: Callable[[str], None]
) -> None:
    make_user("fay@example.com")
    login("fay@example.com")
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "short"},
    )
    assert r.status_code == 422
