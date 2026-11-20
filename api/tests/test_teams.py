"""Teams, their links, and creating their repo / Linear team / Coolify project.

Outside services are never called: ``fake_http`` replaces ``app.core.http.request_json``.
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import http
from app.core.naming import best_match
from app.users.models import User


class FakeHttp:
    """Stands in for ``http.request_json``. Register a response per (method, url).

    A response can be a value to return, an ``HttpError`` to raise, or a function
    of the request body (for GraphQL, where every request goes to one URL).
    """

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], Any] = {}
        self.calls: list[tuple[str, str, Any, dict[str, str]]] = []

    def on(self, method: str, url: str, response: Any) -> None:
        self.routes[(method, url)] = response

    def __call__(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: Any = None,
        timeout: float = 0,
    ) -> Any:
        self.calls.append((method, url, body, headers or {}))
        if (method, url) not in self.routes:
            raise AssertionError(f"Unexpected request: {method} {url}")
        response = self.routes[(method, url)]
        if isinstance(response, http.HttpError):
            raise response
        return response(body) if callable(response) else response


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch) -> FakeHttp:
    fake = FakeHttp()
    monkeypatch.setattr(http, "request_json", fake)
    return fake


@pytest.fixture
def staff(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> TestClient:
    """A logged-in superuser (they can set shared keys too)."""
    make_user("staff@example.com", is_superuser=True)
    login("staff@example.com")
    return client


def _create_team(client: TestClient, name: str) -> dict[str, Any]:
    r = client.post("/api/teams", json={"name": name})
    assert r.status_code == 201, r.text
    team: dict[str, Any] = r.json()
    return team


ORG_REPOS = "https://api.github.com/orgs/cs-course/repos?per_page=100&page=1"


def _set_keys(client: TestClient, system: dict[str, str], mine: dict[str, str]) -> None:
    for key, value in system.items():
        assert client.put(f"/api/credentials/system/{key}", json={"value": value}).is_success
    for key, value in mine.items():
        assert client.put(f"/api/credentials/me/{key}", json={"value": value}).is_success


# --- Teams ------------------------------------------------------------------


def test_teams_require_login(client: TestClient) -> None:
    assert client.get("/api/teams").status_code == 401
    assert client.post("/api/teams", json={"name": "A"}).status_code == 401
    assert client.get("/api/teams/services").status_code == 401


def test_create_rename_and_delete_teams(staff: TestClient) -> None:
    beta = _create_team(staff, "  Team   Beta ")
    assert beta["name"] == "Team Beta"  # spaces tidied
    assert beta["links"] == []
    alpha = _create_team(staff, "Team Alpha")

    # Names are unique, ignoring case.
    r = staff.post("/api/teams", json={"name": "team alpha"})
    assert r.status_code == 409
    assert r.json()["detail"] == "There's already a team called team alpha."
    assert staff.post("/api/teams", json={"name": "   "}).status_code == 422

    assert [t["name"] for t in staff.get("/api/teams").json()] == ["Team Alpha", "Team Beta"]

    assert staff.patch(f"/api/teams/{beta['id']}", json={"name": "Team Alpha"}).status_code == 409
    # Changing only the capitalization of your own name is fine.
    r = staff.patch(f"/api/teams/{alpha['id']}", json={"name": "TEAM ALPHA"})
    assert r.status_code == 200
    assert r.json()["name"] == "TEAM ALPHA"

    assert staff.delete(f"/api/teams/{alpha['id']}").status_code == 204
    assert [t["name"] for t in staff.get("/api/teams").json()] == ["Team Beta"]
    assert staff.delete(f"/api/teams/{alpha['id']}").status_code == 404


def test_regular_users_can_manage_teams(
    client: TestClient, make_user: Callable[..., User], login: Callable[[str], None]
) -> None:
    make_user("ta@example.com")
    login("ta@example.com")
    assert _create_team(client, "Team A")["name"] == "Team A"


# --- Links ------------------------------------------------------------------


def test_custom_links(staff: TestClient) -> None:
    team = _create_team(staff, "Team A")
    url = f"/api/teams/{team['id']}/links"

    r = staff.post(url, json={"label": "Figma", "url": "https://figma.com/file/abc"})
    assert r.status_code == 201, r.text
    [link] = r.json()["links"]
    assert link["label"] == "Figma"
    assert link["service_id"] is None

    # Any number of custom links, but each needs a name and a real web address.
    staff.post(url, json={"label": "Slack", "url": "https://slack.com/x"})
    assert staff.post(url, json={"url": "https://example.com"}).status_code == 422
    assert staff.post(url, json={"label": "Bad", "url": "figma.com"}).status_code == 422
    assert staff.post(url, json={"label": "Bad", "url": "javascript:alert(1)"}).status_code == 422

    r = staff.patch(f"{url}/{link['id']}", json={"label": "Designs", "url": "https://figma.com/2"})
    assert r.status_code == 200
    assert r.json()["links"][0] == {**link, "label": "Designs", "url": "https://figma.com/2"}

    r = staff.delete(f"{url}/{link['id']}")
    assert r.status_code == 200
    assert [x["label"] for x in r.json()["links"]] == ["Slack"]
    assert staff.delete(f"{url}/{link['id']}").status_code == 404


def test_link_an_existing_repo_by_url(staff: TestClient) -> None:
    team = _create_team(staff, "Team A")
    url = f"/api/teams/{team['id']}/links"
    body = {"service_id": "github", "url": "https://github.com/org/old-repo"}

    r = staff.post(url, json=body)
    assert r.status_code == 201, r.text
    [link] = r.json()["links"]
    assert (link["service_id"], link["label"]) == ("github", "GitHub")

    r = staff.post(url, json=body)
    assert r.status_code == 409
    assert r.json()["detail"] == "Team A already has a GitHub repository."
    assert staff.post(url, json={**body, "service_id": "nope"}).status_code == 404


def test_deleting_a_team_deletes_its_links(staff: TestClient) -> None:
    team = _create_team(staff, "Team A")
    staff.post(f"/api/teams/{team['id']}/links", json={"label": "X", "url": "https://x.test"})
    assert staff.delete(f"/api/teams/{team['id']}").status_code == 204
    # Same name can be used again, and starts with no links.
    assert _create_team(staff, "Team A")["links"] == []


# --- Services ---------------------------------------------------------------


def test_services_list_github_linear_and_coolify(staff: TestClient) -> None:
    services = staff.get("/api/teams/services").json()
    assert [s["id"] for s in services] == ["github", "linear", "coolify"]
    github = services[0]
    assert github["resource_name"] == "repository"
    assert github["configured"] is False
    assert github["message"] == (
        "Add the GitHub personal access token and GitHub organization in System settings."
    )


def test_service_needs_keys_first(staff: TestClient, fake_http: FakeHttp) -> None:
    team = _create_team(staff, "Team A")
    r = staff.post(f"/api/teams/{team['id']}/services/github")
    assert r.status_code == 400
    assert "System settings" in r.json()["detail"]
    assert fake_http.calls == []
    assert staff.post(f"/api/teams/{team['id']}/services/nope").status_code == 404


def test_github_creates_private_repo_in_org(staff: TestClient, fake_http: FakeHttp) -> None:
    _set_keys(
        staff,
        system={"github_org": "https://github.com/cs-course/"},  # pasted URL is fine
        mine={"github_token": "github_pat_secret_value"},
    )
    team = _create_team(staff, "Team Alpha!")
    fake_http.on(
        "GET",
        "https://api.github.com/repos/cs-course/team-alpha",
        http.HttpError(404, {"message": "Not Found"}),
    )
    fake_http.on("GET", ORG_REPOS, [{"id": 1, "name": "starter-code"}])
    fake_http.on(
        "POST",
        "https://api.github.com/orgs/cs-course/repos",
        {
            "id": 42,
            "full_name": "cs-course/team-alpha",
            "html_url": "https://github.com/cs-course/team-alpha",
        },
    )

    r = staff.post(f"/api/teams/{team['id']}/services/github")
    assert r.status_code == 200, r.text
    assert r.json()["message"] == "Created the GitHub repository cs-course/team-alpha."
    [link] = r.json()["team"]["links"]
    assert link["service_id"] == "github"
    assert link["url"] == "https://github.com/cs-course/team-alpha"

    method, _, body, headers = fake_http.calls[-1]
    assert method == "POST"
    assert body["name"] == "team-alpha"
    assert body["private"] is True
    assert headers["Authorization"] == "Bearer github_pat_secret_value"

    # Clicking again doesn't make a second repo.
    calls = len(fake_http.calls)
    r = staff.post(f"/api/teams/{team['id']}/services/github")
    assert r.status_code == 409
    assert len(fake_http.calls) == calls


def test_github_finds_repos_named_after_the_team(staff: TestClient, fake_http: FakeHttp) -> None:
    _set_keys(staff, system={"github_org": "cs-course"}, mine={"github_token": "github_pat_x"})
    fake_http.on(
        "GET", "https://api.github.com/repos/cs-course/before-dawn", http.HttpError(404, None)
    )
    fake_http.on(
        "GET",
        ORG_REPOS,
        [
            {"id": 1, "name": "LeapfrogArchitecturePatterns", "full_name": "cs-course/Leapfrog"},
            {
                "id": 2,
                "name": "BeforeDawnArchitecturePatterns",
                "full_name": "cs-course/BeforeDawnArchitecturePatterns",
                "html_url": "https://github.com/cs-course/BeforeDawnArchitecturePatterns",
            },
        ],
    )
    team = _create_team(staff, "Before Dawn")

    # The create button links it rather than making a new "before-dawn" repo.
    r = staff.post(f"/api/teams/{team['id']}/services/github")
    assert r.status_code == 200, r.text
    assert r.json()["message"] == (
        "Linked the existing GitHub repository cs-course/BeforeDawnArchitecturePatterns."
    )
    assert "POST" not in {method for method, *_ in fake_http.calls}


def test_github_links_a_repo_that_already_exists(staff: TestClient, fake_http: FakeHttp) -> None:
    _set_keys(staff, system={"github_org": "cs-course"}, mine={"github_token": "github_pat_x"})
    repo = {
        "id": 7,
        "full_name": "cs-course/team-a",
        "html_url": "https://github.com/cs-course/team-a",
    }
    fake_http.on("GET", "https://api.github.com/repos/cs-course/team-a", repo)
    a = _create_team(staff, "Team A")

    r = staff.post(f"/api/teams/{a['id']}/services/github")
    assert r.status_code == 200, r.text
    assert r.json()["message"] == "Linked the existing GitHub repository cs-course/team-a."

    # "team a" can't be made, but "Team-A" gives the same repo name; it's already Team A's.
    b = _create_team(staff, "Team-A")
    r = staff.post(f"/api/teams/{b['id']}/services/github")
    assert r.status_code == 409
    assert r.json()["detail"] == (
        "The GitHub repository cs-course/team-a is already linked to Team A."
    )
    assert staff.get("/api/teams").json()[1]["links"] == []


def test_github_errors_are_shown_and_nothing_is_saved(
    staff: TestClient, fake_http: FakeHttp
) -> None:
    _set_keys(staff, system={"github_org": "cs-course"}, mine={"github_token": "github_pat_x"})
    team = _create_team(staff, "Team A")
    fake_http.on("GET", "https://api.github.com/repos/cs-course/team-a", http.HttpError(404, None))
    fake_http.on("GET", ORG_REPOS, [])
    fake_http.on(
        "POST",
        "https://api.github.com/orgs/cs-course/repos",
        http.HttpError(403, {"message": "Resource not accessible by personal access token"}),
    )

    r = staff.post(f"/api/teams/{team['id']}/services/github")
    assert r.status_code == 502
    assert "isn't allowed to create repositories in 'cs-course'" in r.json()["detail"]
    assert "github_pat_x" not in r.text
    assert staff.get("/api/teams").json()[0]["links"] == []


def test_linear_creates_team(staff: TestClient, fake_http: FakeHttp) -> None:
    _set_keys(staff, system={}, mine={"linear_api_key": "lin_api_secret"})
    team = _create_team(staff, "Team Alpha")

    def graphql(body: dict[str, Any]) -> dict[str, Any]:
        if "teamCreate" in body["query"]:
            assert body["variables"] == {"input": {"name": "Team Alpha"}}
            return {
                "data": {
                    "teamCreate": {
                        "success": True,
                        "team": {"id": "lin-1", "key": "TEA", "name": "Team Alpha"},
                    }
                }
            }
        return {
            "data": {
                "organization": {"urlKey": "my-course"},
                "teams": {"nodes": [{"id": "lin-0", "key": "ENG", "name": "Engineering"}]},
            }
        }

    fake_http.on("POST", "https://api.linear.app/graphql", graphql)

    r = staff.post(f"/api/teams/{team['id']}/services/linear")
    assert r.status_code == 200, r.text
    assert r.json()["message"] == "Created the Linear team Team Alpha (TEA)."
    assert r.json()["team"]["links"][0]["url"] == "https://linear.app/my-course/team/TEA"
    assert fake_http.calls[0][3]["Authorization"] == "lin_api_secret"


def test_linear_links_existing_team_and_reports_errors(
    staff: TestClient, fake_http: FakeHttp
) -> None:
    _set_keys(staff, system={}, mine={"linear_api_key": "lin_api_secret"})
    a = _create_team(staff, "Team A")
    b = _create_team(staff, "Team B")
    fake_http.on(
        "POST",
        "https://api.linear.app/graphql",
        lambda body: (
            {
                "data": {
                    "organization": {"urlKey": "acme"},
                    "teams": {"nodes": [{"id": "lin-a", "key": "TA", "name": "team a"}]},
                }
            }
            if "teamCreate" not in body["query"]
            else {
                "errors": [{"message": "x", "extensions": {"userPresentableMessage": "No access"}}]
            }
        ),
    )

    r = staff.post(f"/api/teams/{a['id']}/services/linear")
    assert r.json()["message"] == "Linked the existing Linear team team a (TA)."

    r = staff.post(f"/api/teams/{b['id']}/services/linear")
    assert r.status_code == 502
    assert r.json()["detail"] == "Linear error: No access"


DROPLETS_URL = "https://api.digitalocean.com/v2/droplets?per_page=200"


def _droplet(id_: int, name: str, ip: str | None, tags: list[str] | None = None) -> dict[str, Any]:
    v4 = [{"ip_address": ip, "type": "public"}] if ip else []
    v4.append({"ip_address": "10.10.0.2", "type": "private"})
    return {"id": id_, "name": name, "tags": tags or [], "networks": {"v4": v4}}


def _droplets(*droplets: dict[str, Any]) -> dict[str, Any]:
    return {"droplets": list(droplets), "links": {}}


def _coolify_keys(client: TestClient) -> None:
    _set_keys(
        client,
        system={"coolify_url": "coolify.test/"},
        mine={"digitalocean_token": "dop_v1_secret_token"},
    )


def test_coolify_links_the_teams_droplet(staff: TestClient, fake_http: FakeHttp) -> None:
    _coolify_keys(staff)
    fake_http.on(
        "GET",
        DROPLETS_URL,
        _droplets(
            _droplet(1, "coolify-control-plane-droplet", "203.0.113.1"),
            _droplet(2, "BeforeDawn", "203.0.113.2"),
            _droplet(3, "Leapfrog", "203.0.113.3"),
        ),
    )
    team = _create_team(staff, "Before Dawn")

    r = staff.post(f"/api/teams/{team['id']}/services/coolify")
    assert r.status_code == 200, r.text
    assert r.json()["message"] == "Linked the existing Coolify server BeforeDawn · 203.0.113.2."
    [link] = r.json()["team"]["links"]
    assert link["url"] == "https://coolify.test"  # Coolify's dashboard; teams are picked there
    assert link["label"] == "BeforeDawn · 203.0.113.2"
    assert fake_http.calls[0][3]["Authorization"] == "Bearer dop_v1_secret_token"
    # Droplets are only ever read.
    assert {method for method, *_ in fake_http.calls} == {"GET"}


def test_coolify_finds_droplets_by_tag_on_any_page(staff: TestClient, fake_http: FakeHttp) -> None:
    _coolify_keys(staff)
    page_2 = "https://api.digitalocean.com/v2/droplets?page=2&per_page=200"
    fake_http.on(
        "GET",
        DROPLETS_URL,
        {"droplets": [_droplet(1, "web-1", "203.0.113.1")], "links": {"pages": {"next": page_2}}},
    )
    fake_http.on("GET", page_2, _droplets(_droplet(7, "srv-7", "203.0.113.7", tags=["team-a"])))

    coolify = staff.get("/api/teams/lookup", params={"name": "Team A"}).json()["services"][2]
    assert coolify["found"]["label"] == "srv-7 · 203.0.113.7"
    assert coolify["found"]["external_id"] == "7"


def test_coolify_never_creates_servers(staff: TestClient, fake_http: FakeHttp) -> None:
    _coolify_keys(staff)
    fake_http.on("GET", DROPLETS_URL, _droplets(_droplet(1, "Leapfrog", "203.0.113.1")))
    team = _create_team(staff, "Team Z")

    services = {s["id"]: s for s in staff.get("/api/teams/services").json()}
    assert services["coolify"]["can_create"] is False
    assert services["github"]["can_create"] is True

    r = staff.post(f"/api/teams/{team['id']}/services/coolify")
    assert r.status_code == 404
    assert r.json()["detail"].startswith("No Coolify server found for Team Z.")
    assert {method for method, *_ in fake_http.calls} == {"GET"}


def test_coolify_reports_digitalocean_errors(staff: TestClient, fake_http: FakeHttp) -> None:
    _coolify_keys(staff)
    fake_http.on(
        "GET",
        DROPLETS_URL,
        http.HttpError(401, {"id": "unauthorized", "message": "Unable to auth"}),
    )
    coolify = staff.get("/api/teams/lookup", params={"name": "Team A"}).json()["services"][2]
    assert coolify["error"] == "DigitalOcean rejected your API token. Replace it with a valid one."
    assert "dop_v1_secret_token" not in str(coolify)


# --- Filling in the "Add team" form -------------------------------------------


def _all_keys(client: TestClient) -> None:
    _set_keys(
        client,
        system={"github_org": "cs-course", "coolify_url": "https://coolify.test"},
        mine={
            "github_token": "github_pat_x",
            "linear_api_key": "lin_api_x",
            "digitalocean_token": "dop_v1_secret_token",
        },
    )


def _linear_teams(*nodes: dict[str, str]) -> Callable[[Any], Any]:
    return lambda body: {
        "data": {"organization": {"urlKey": "acme"}, "teams": {"nodes": list(nodes)}}
    }


def test_lookup_finds_existing_things_by_name(staff: TestClient, fake_http: FakeHttp) -> None:
    _all_keys(staff)
    fake_http.on(
        "GET",
        "https://api.github.com/repos/cs-course/team-alpha",
        {
            "id": 5,
            "full_name": "cs-course/team-alpha",
            "html_url": "https://github.com/cs-course/team-alpha",
        },
    )
    # Different spellings of the name still match.
    fake_http.on(
        "POST",
        "https://api.linear.app/graphql",
        _linear_teams({"id": "lin-1", "key": "ALP", "name": "team-alpha"}),
    )
    fake_http.on("GET", DROPLETS_URL, _droplets(_droplet(1, "Other", "203.0.113.1")))

    r = staff.get("/api/teams/lookup", params={"name": "  Team   Alpha "})
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["name"] == "Team Alpha"
    assert result["name_taken"] is False
    github, linear, coolify = result["services"]
    assert github == {
        "service_id": "github",
        "configured": True,
        "found": {
            "url": "https://github.com/cs-course/team-alpha",
            "label": "cs-course/team-alpha",
            "external_id": "5",
        },
        "linked_team": None,
        "error": None,
    }
    assert linear["found"]["url"] == "https://linear.app/acme/team/ALP"
    assert coolify["found"] is None
    assert coolify["error"] is None
    # Nothing was created anywhere.
    assert {m for m, *_ in fake_http.calls} == {"GET", "POST"}
    assert all("teamCreate" not in str(body) for _, _, body, _ in fake_http.calls)


def test_lookup_reports_each_service_separately(staff: TestClient, fake_http: FakeHttp) -> None:
    # Only Linear is set up, and Coolify's server is missing.
    _set_keys(staff, system={}, mine={"linear_api_key": "lin_api_x"})
    fake_http.on(
        "POST",
        "https://api.linear.app/graphql",
        http.HttpError(400, {"errors": [{"message": "Authentication required"}]}),
    )
    _create_team(staff, "Team Alpha")

    result = staff.get("/api/teams/lookup", params={"name": "team alpha"}).json()
    assert result["name_taken"] is True
    github, linear, coolify = result["services"]
    assert github["configured"] is False
    assert github["error"] == (
        "Add the GitHub personal access token and GitHub organization in System settings."
    )
    assert linear["configured"] is True
    assert linear["error"] == "Linear error: Authentication required"
    assert coolify["configured"] is False
    assert staff.get("/api/teams/lookup", params={"name": "   "}).status_code == 422


def test_lookup_flags_things_already_linked_to_another_team(
    staff: TestClient, fake_http: FakeHttp
) -> None:
    _all_keys(staff)
    fake_http.on("GET", DROPLETS_URL, _droplets(_droplet(31, "TeamA", "203.0.113.31")))
    a = _create_team(staff, "Team A")
    assert staff.post(f"/api/teams/{a['id']}/services/coolify").status_code == 200

    fake_http.on("GET", "https://api.github.com/repos/cs-course/team-a", http.HttpError(404))
    fake_http.on("GET", ORG_REPOS, [])
    fake_http.on("POST", "https://api.linear.app/graphql", _linear_teams())
    coolify = staff.get("/api/teams/lookup", params={"name": "team-a"}).json()["services"][2]
    assert coolify["found"]["external_id"] == "31"
    assert coolify["linked_team"] == "Team A"


def test_find_links_connects_what_already_exists(staff: TestClient, fake_http: FakeHttp) -> None:
    _all_keys(staff)
    fake_http.on("GET", "https://api.github.com/repos/cs-course/before-dawn", http.HttpError(404))
    fake_http.on(
        "GET",
        ORG_REPOS,
        [
            {
                "id": 9,
                "name": "BeforeDawnArchitecturePatterns",
                "full_name": "cs-course/BeforeDawnArchitecturePatterns",
                "html_url": "https://github.com/cs-course/BeforeDawnArchitecturePatterns",
            }
        ],
    )
    fake_http.on("POST", "https://api.linear.app/graphql", _linear_teams())
    fake_http.on("GET", DROPLETS_URL, _droplets(_droplet(2, "BeforeDawn", "203.0.113.2")))
    team = _create_team(staff, "Before Dawn")

    r = staff.post(f"/api/teams/{team['id']}/connect")
    assert r.status_code == 200, r.text
    outcomes = {x["service_id"]: (x["outcome"], x["message"]) for x in r.json()["results"]}
    assert outcomes == {
        "github": ("linked", "Linked cs-course/BeforeDawnArchitecturePatterns."),
        "linear": ("not_found", "No Linear team found for Before Dawn."),
        "coolify": ("linked", "Linked BeforeDawn · 203.0.113.2."),
    }
    links = {x["service_id"]: x["label"] for x in r.json()["team"]["links"]}
    assert links == {
        "github": "cs-course/BeforeDawnArchitecturePatterns",
        "coolify": "BeforeDawn · 203.0.113.2",
    }
    # Nothing was created anywhere.
    assert "teamCreate" not in str(fake_http.calls)
    assert {m for m, url, *_ in fake_http.calls if "github" in url} == {"GET"}

    # Running it again changes nothing.
    again = staff.post(f"/api/teams/{team['id']}/connect").json()
    assert [x["outcome"] for x in again["results"]] == [
        "already_linked",
        "not_found",
        "already_linked",
    ]
    assert len(again["team"]["links"]) == 2


def test_create_team_with_all_its_links_at_once(staff: TestClient) -> None:
    r = staff.post(
        "/api/teams",
        json={
            "name": "Team Alpha",
            "links": [
                {
                    "service_id": "github",
                    "url": "https://github.com/cs-course/team-alpha",
                    "external_id": "5",
                },
                {"service_id": "coolify", "url": "https://coolify.test/project/c1"},
                {"label": "Figma", "url": "https://figma.com/file/x"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    links = r.json()["links"]
    assert [(x["service_id"], x["label"]) for x in links] == [
        ("github", "GitHub"),
        ("coolify", "Coolify"),
        (None, "Figma"),
    ]

    # The same repo can't go to a second team; nothing is saved if one link is refused.
    r = staff.post(
        "/api/teams",
        json={
            "name": "Team Beta",
            "links": [
                {"label": "Docs", "url": "https://docs.test"},
                {"service_id": "github", "url": "https://github.com/x", "external_id": "5"},
            ],
        },
    )
    assert r.status_code == 409
    assert r.json()["detail"].endswith("is already linked to Team Alpha.")
    assert [t["name"] for t in staff.get("/api/teams").json()] == ["Team Alpha"]

    two_githubs = [
        {"service_id": "github", "url": "https://github.com/a"},
        {"service_id": "github", "url": "https://github.com/b"},
    ]
    assert staff.post("/api/teams", json={"name": "C", "links": two_githubs}).status_code == 422
    bad = [{"service_id": "nope", "url": "https://x.test"}]
    assert staff.post("/api/teams", json={"name": "C", "links": bad}).status_code == 404


def _match(name: str, *candidates: str) -> str | None:
    return best_match(name, candidates, names=lambda c: [c])


def test_best_match_finds_the_teams_thing_but_never_guesses() -> None:
    # Case, spaces, and punctuation don't matter.
    assert _match("Team Alpha", "Other", "team-alpha") == "team-alpha"
    assert _match("Before Dawn", "BeforeDawn") == "BeforeDawn"
    # An exact match wins over longer names.
    assert _match("Nimbus", "NimbusArchitecturePatterns", "nimbus") == "nimbus"
    # Otherwise: the one name starting with the team's, then the one containing it.
    assert (
        _match("Before Dawn", "BeforeDawnArchitecturePatterns") == "BeforeDawnArchitecturePatterns"
    )
    assert _match("Before Dawn", "cs4535-before-dawn", "Leapfrog") == "cs4535-before-dawn"
    # Two equally good candidates: pick neither.
    assert _match("Before Dawn", "BeforeDawnA", "BeforeDawnB") is None
    # Short names are only matched exactly.
    assert _match("Red", "Redwood") is None
    assert _match("!!!", "???") is None


# --- HTTP helper --------------------------------------------------------------


def test_http_helper_only_allows_web_addresses() -> None:
    with pytest.raises(http.HttpError) as info:
        http.request_json("GET", "file:///etc/passwd")
    assert info.value.status == 0
