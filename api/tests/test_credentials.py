from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.credentials.models import Credential
from app.credentials.service import get_system_credential, get_user_credential, save
from app.main import app
from app.users.models import User

GITHUB_TOKEN = "github_pat_abcdefghijklmnop1234"


def _by_key(items: list[dict]) -> dict[str, dict]:  # type: ignore[type-arg]
    return {i["key"]: i for i in items}


def test_user_can_set_and_remove_own_token(
    client: TestClient, db: Session, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    user = make_user("instructor@example.com")
    login("instructor@example.com")

    mine = _by_key(client.get("/api/credentials/me").json())
    assert set(mine) == {"github_token", "linear_api_key", "digitalocean_token"}  # user only
    assert mine["github_token"]["is_set"] is False

    r = client.put("/api/credentials/me/github_token", json={"value": f"  {GITHUB_TOKEN}\n"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_set"] is True
    assert body["hint"] == "1234"
    assert GITHUB_TOKEN not in r.text  # the value is never sent back

    # Stored encrypted, readable through the service.
    row = db.scalar(select(Credential).where(Credential.key == "github_token"))
    assert row is not None
    assert GITHUB_TOKEN not in row.encrypted_value
    assert get_user_credential(db, user, "github_token") == GITHUB_TOKEN

    assert client.delete("/api/credentials/me/github_token").status_code == 204
    assert get_user_credential(db, user, "github_token") is None


def test_credentials_are_private_to_each_user(
    client: TestClient, db: Session, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    make_user("a@example.com")
    b = make_user("b@example.com")
    login("a@example.com")
    client.put("/api/credentials/me/github_token", json={"value": GITHUB_TOKEN})

    assert get_user_credential(db, b, "github_token") is None
    with TestClient(app) as other:
        other.post(
            "/api/auth/login", json={"email": "b@example.com", "password": "correct-horse-battery"}
        )
        theirs = _by_key(other.get("/api/credentials/me").json())
        assert theirs["github_token"]["is_set"] is False


def test_unknown_or_wrong_scope_key_rejected(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    make_user("u@example.com", is_superuser=True)
    login("u@example.com")
    assert client.put("/api/credentials/me/nope", json={"value": "x"}).status_code == 404
    # A system key can't be saved as a personal one, and vice versa.
    assert (
        client.put("/api/credentials/me/anthropic_api_key", json={"value": "x"}).status_code == 404
    )
    assert (
        client.put("/api/credentials/system/github_token", json={"value": "x"}).status_code == 404
    )
    assert client.put("/api/credentials/me/github_token", json={"value": "   "}).status_code == 422


def test_system_credentials_require_superuser(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    make_user("student@example.com")
    login("student@example.com")
    assert client.get("/api/credentials/system").status_code == 403
    r = client.put("/api/credentials/system/anthropic_api_key", json={"value": "sk-ant-x"})
    assert r.status_code == 403
    assert client.delete("/api/credentials/system/anthropic_api_key").status_code == 403


def test_superuser_manages_system_credentials(
    client: TestClient, db: Session, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    make_user("admin@example.com", is_superuser=True)
    login("admin@example.com")

    system = _by_key(client.get("/api/credentials/system").json())
    assert "anthropic_api_key" in system
    assert "github_token" not in system

    key = "sk-ant-api03-secretsecretsecret-WXYZ"
    r = client.put("/api/credentials/system/anthropic_api_key", json={"value": key})
    assert r.status_code == 200
    assert r.json()["hint"] == "WXYZ"
    assert get_system_credential(db, "anthropic_api_key") == key

    # Replacing keeps a single row.
    client.put("/api/credentials/system/anthropic_api_key", json={"value": key + "2"})
    assert get_system_credential(db, "anthropic_api_key") == key + "2"
    assert len(list(db.scalars(select(Credential)))) == 1

    assert client.delete("/api/credentials/system/anthropic_api_key").status_code == 204
    assert get_system_credential(db, "anthropic_api_key") is None


def test_undecryptable_value_is_reported(
    client: TestClient, db: Session, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    user = make_user("u@example.com")
    login("u@example.com")
    client.put("/api/credentials/me/github_token", json={"value": GITHUB_TOKEN})
    row = db.scalar(select(Credential))
    assert row is not None
    row.encrypted_value = "garbage-from-an-old-secret-key"
    db.commit()

    status = _by_key(client.get("/api/credentials/me").json())["github_token"]
    assert status["is_set"] is True
    assert status["readable"] is False
    assert get_user_credential(db, user, "github_token") is None


def test_tool_status_follows_user_token(
    client: TestClient, db: Session, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    user = make_user("u@example.com")
    login("u@example.com")

    status = client.get("/api/tools/github/status").json()
    assert status["configured"] is False
    assert status["missing_user_credentials"] == ["github_token"]
    assert status["missing_system_credentials"] == ["github_org"]

    client.put("/api/credentials/me/github_token", json={"value": GITHUB_TOKEN})
    status = client.get("/api/tools/github/status").json()
    assert status["missing_user_credentials"] == []
    assert status["configured"] is False  # an administrator still has to set the org

    save(db, user_id=None, key="github_org", value="my-course-org", updated_by=user)
    assert client.get("/api/tools/github/status").json()["configured"] is True
    tools = {t["id"]: t["configured"] for t in client.get("/api/tools").json()}
    assert tools == {"github": True, "linear": False, "coolify": False}
