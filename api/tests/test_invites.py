from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.invites.models import Invite
from app.main import app
from app.users.models import User


def _admin(make_user: Callable[..., User], login: Callable[[str], None]) -> None:
    make_user("admin@example.com", is_superuser=True)
    login("admin@example.com")


def _invite(client: TestClient, email: str = "new@example.com", **extra: object) -> dict:  # type: ignore[type-arg]
    r = client.post("/api/invites", json={"email": email, "full_name": "New Person", **extra})
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def test_only_superusers_manage_invites(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    assert client.get("/api/invites").status_code == 401
    make_user("student@example.com")
    login("student@example.com")
    assert client.get("/api/invites").status_code == 403
    assert client.post("/api/invites", json={"email": "x@example.com"}).status_code == 403


def test_create_invite_returns_token_once(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    _admin(make_user, login)
    created = _invite(client, "New@Example.com")
    assert created["email"] == "new@example.com"
    assert created["status"] == "pending"
    assert created["created_by_email"] == "admin@example.com"
    assert len(created["token"]) > 30

    listed = client.get("/api/invites").json()
    assert len(listed) == 1
    assert "token" not in listed[0]


def test_cannot_invite_existing_user(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    _admin(make_user, login)
    r = client.post("/api/invites", json={"email": "admin@example.com"})
    assert r.status_code == 409


def test_accept_invite_creates_user_and_logs_in(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    _admin(make_user, login)
    token = _invite(client, is_superuser=True)["token"]

    with TestClient(app) as guest:
        preview = guest.get(f"/api/invites/accept/{token}")
        assert preview.status_code == 200
        assert preview.json()["email"] == "new@example.com"
        assert preview.json()["full_name"] == "New Person"

        r = guest.post(
            f"/api/invites/accept/{token}",
            json={"full_name": "Chosen Name", "password": "a-good-password"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["full_name"] == "Chosen Name"
        assert r.json()["is_superuser"] is True

        # Logged in immediately.
        assert guest.get("/api/auth/me").json()["email"] == "new@example.com"

        # Single use.
        r = guest.get(f"/api/invites/accept/{token}")
        assert r.status_code == 410
        assert "already been used" in r.json()["detail"]
        r = guest.post(f"/api/invites/accept/{token}", json={"password": "a-good-password"})
        assert r.status_code == 410

    statuses = [i["status"] for i in client.get("/api/invites").json()]
    assert statuses == ["accepted"]


def test_accept_requires_valid_password(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    _admin(make_user, login)
    token = _invite(client)["token"]
    r = client.post(f"/api/invites/accept/{token}", json={"password": "short"})
    assert r.status_code == 422


def test_unknown_token(client: TestClient) -> None:
    r = client.get("/api/invites/accept/not-a-real-token")
    assert r.status_code == 404


def test_revoked_invite_cannot_be_used(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    _admin(make_user, login)
    created = _invite(client)
    r = client.post(f"/api/invites/{created['id']}/revoke")
    assert r.json()["status"] == "revoked"

    r = client.get(f"/api/invites/accept/{created['token']}")
    assert r.status_code == 410
    assert "cancelled" in r.json()["detail"]


def test_expired_invite_cannot_be_used(
    client: TestClient,
    db: Session,
    make_user: Callable[..., User],
    login: Callable[[str], None],
) -> None:
    _admin(make_user, login)
    created = _invite(client)
    invite = db.get(Invite, created["id"])
    assert invite is not None
    invite.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    r = client.get(f"/api/invites/accept/{created['token']}")
    assert r.status_code == 410
    assert "expired" in r.json()["detail"]
    assert client.get("/api/invites").json()[0]["status"] == "expired"


def test_new_invite_replaces_pending_one(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    _admin(make_user, login)
    first = _invite(client)
    second = _invite(client)

    assert client.get(f"/api/invites/accept/{first['token']}").status_code == 410
    assert client.get(f"/api/invites/accept/{second['token']}").status_code == 200
    statuses = {i["id"]: i["status"] for i in client.get("/api/invites").json()}
    assert statuses == {first["id"]: "revoked", second["id"]: "pending"}
