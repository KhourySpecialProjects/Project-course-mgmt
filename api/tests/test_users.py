from collections.abc import Callable

from fastapi.testclient import TestClient

from app.users.models import User


def test_regular_user_cannot_list_users(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    make_user("student@example.com")
    login("student@example.com")
    assert client.get("/api/users").status_code == 403


def test_superuser_can_create_and_list_users(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    make_user("admin@example.com", is_superuser=True)
    login("admin@example.com")

    r = client.post(
        "/api/users",
        json={"email": "New@Example.com", "full_name": "New Person", "password": "password123"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "new@example.com"
    assert r.json()["is_superuser"] is False

    emails = [u["email"] for u in client.get("/api/users").json()]
    assert emails == ["admin@example.com", "new@example.com"]


def test_duplicate_email_rejected(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    make_user("admin@example.com", is_superuser=True)
    login("admin@example.com")
    body = {"email": "admin@example.com", "password": "password123"}
    assert client.post("/api/users", json=body).status_code == 409


def test_superuser_cannot_deactivate_self(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    admin = make_user("admin@example.com", is_superuser=True)
    login("admin@example.com")
    r = client.patch(f"/api/users/{admin.id}", json={"is_active": False})
    assert r.status_code == 400


def test_deactivating_user_logs_them_out(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    make_user("admin@example.com", is_superuser=True)
    target = make_user("target@example.com")

    # Log the target in with a separate client (a separate "browser").
    from app.main import app

    with TestClient(app) as other:
        r = other.post(
            "/api/auth/login",
            json={"email": "target@example.com", "password": "correct-horse-battery"},
        )
        assert r.status_code == 200

        login("admin@example.com")
        r = client.patch(f"/api/users/{target.id}", json={"is_active": False})
        assert r.status_code == 200
        assert r.json()["is_active"] is False

        assert other.get("/api/auth/me").status_code == 401
