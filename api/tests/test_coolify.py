from collections.abc import Callable

from fastapi.testclient import TestClient

from app.users.models import User


def test_coolify_status_requires_login(client: TestClient) -> None:
    assert client.get("/api/tools/coolify/status").status_code == 401


def test_coolify_needs_server_url_and_personal_token(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    make_user("admin@example.com", is_superuser=True)
    login("admin@example.com")

    status = client.get("/api/tools/coolify/status").json()
    assert status["configured"] is False
    assert status["missing_system_credentials"] == ["coolify_url"]
    assert status["missing_user_credentials"] == ["coolify_token"]
    # Superusers have every key in System settings, so that's the only place mentioned.
    assert status["message"] == (
        "Add the Coolify server URL and Coolify API token in System settings."
    )

    # The server URL is shared, so an administrator sets it once in System settings.
    r = client.put("/api/credentials/system/coolify_url", json={"value": "https://coolify.test"})
    assert r.status_code == 200
    status = client.get("/api/tools/coolify/status").json()
    assert status["configured"] is False
    assert status["missing_system_credentials"] == []
    assert status["missing_user_credentials"] == ["coolify_token"]

    # The token is personal, so each user adds their own.
    r = client.put("/api/credentials/me/coolify_token", json={"value": "1|abcdefghijklmnop"})
    assert r.status_code == 200
    assert client.get("/api/tools/coolify/status").json()["configured"] is True


def test_coolify_status_tells_regular_users_where_each_key_goes(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    make_user("instructor@example.com")
    login("instructor@example.com")

    message = client.get("/api/tools/coolify/status").json()["message"]
    assert message == (
        "Add your Coolify API token on your Account page (API keys tab). "
        "An administrator needs to add the Coolify server URL in System settings."
    )
