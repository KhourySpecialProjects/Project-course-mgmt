"""Team updates: recent GitHub activity (linked and deployed repos) and Linear progress."""

from typing import Any

from fastapi.testclient import TestClient

from app.core import http
from tests.conftest import FakeHttp

GH = "https://api.github.com"
C = "https://coolify.test/api/v1"


def _team(client: TestClient, links: list[dict[str, Any]]) -> dict[str, Any]:
    r = client.post("/api/teams", json={"name": "Before Dawn", "links": links})
    assert r.status_code == 201, r.text
    team: dict[str, Any] = r.json()
    return team


def _repo(fake: FakeHttp, full: str, *, commits: int = 2) -> None:
    fake.on(
        "GET",
        f"{GH}/repos/{full}",
        {
            "full_name": full,
            "html_url": f"https://github.com/{full}",
            "private": True,
            "default_branch": "main",
            "pushed_at": "2026-11-20T10:00:00Z",
            "open_issues_count": 3,
        },
    )
    fake.on(
        "GET",
        f"{GH}/repos/{full}/commits?per_page=30&sha=main",
        [
            {
                "sha": f"abc{i}def",
                "html_url": f"https://github.com/{full}/commit/{i}",
                "author": {"login": "student1"},
                "commit": {
                    "message": f"Fix thing {i}\n\nDetails",
                    "committer": {"date": "2026-11-20T10:00:00Z"},
                },
            }
            for i in range(commits)
        ],
    )
    fake.on(
        "GET",
        f"{GH}/repos/{full}/pulls?state=open&per_page=20&sort=updated",
        [
            {
                "number": 7,
                "title": "Add navbar",
                "user": {"login": "student2"},
                "state": "open",
                "draft": False,
                "updated_at": "2026-11-21T09:00:00Z",
                "html_url": "https://github.com/x/pull/7",
            }
        ],
    )
    fake.on(
        "GET",
        f"{GH}/repos/{full}/pulls?state=closed&per_page=10&sort=updated&direction=desc",
        [
            {
                "number": 6,
                "title": "Login page",
                "user": {"login": "student1"},
                "state": "closed",
                "merged_at": "2026-11-19T12:00:00Z",
                "updated_at": "2026-11-19T12:00:00Z",
            },
            {"number": 5, "title": "Abandoned", "state": "closed", "merged_at": None},
        ],
    )


def test_github_updates_cover_linked_and_deployed_repos(
    staff: TestClient, fake_http: FakeHttp
) -> None:
    staff.put("/api/credentials/me/github_token", json={"value": "github_pat_secret_value"})
    staff.put("/api/credentials/system/coolify_url", json={"value": "https://coolify.test"})
    team = _team(
        staff,
        [{"service_id": "github", "url": "https://github.com/org/BeforeDawnArchitecturePatterns"}],
    )
    staff.put(
        f"/api/teams/{team['id']}/credentials/coolify_team_token",
        json={"value": "1|team-token-abcdefgh"},
    )
    fake_http.on(
        "GET",
        f"{C}/applications",
        [
            {"uuid": "a1", "git_repository": "org/ssa-portal", "git_branch": "dev"},
            {
                "uuid": "a2",
                "git_repository": "https://github.com/org/ssa-portal.git",
                "git_branch": "main",
            },
        ],
    )
    _repo(fake_http, "org/BeforeDawnArchitecturePatterns")
    fake_http.on("GET", f"{GH}/repos/org/ssa-portal", http.HttpError(404, {"message": "Not Found"}))

    r = staff.get(f"/api/tools/github/teams/{team['id']}/updates")
    assert r.status_code == 200, r.text
    linked, deployed = r.json()
    assert linked["source"] == "Linked on the team card"
    assert [c["message"] for c in linked["commits"]] == ["Fix thing 0", "Fix thing 1"]
    assert linked["open_pulls"][0]["title"] == "Add navbar"
    assert [p["number"] for p in linked["recent_merged"]] == [
        6
    ]  # closed without merging isn't listed
    assert linked["open_issues"] == 2  # GitHub counts the open pull request as an issue too

    assert deployed["full_name"] == "org/ssa-portal"
    assert deployed["source"] == "Coolify deploys dev, main"
    assert "can't see a private repository" in deployed["error"]
    assert "github_pat_secret_value" not in r.text


def test_linear_updates(staff: TestClient, fake_http: FakeHttp) -> None:
    staff.put("/api/credentials/me/linear_api_key", json={"value": "lin_api_secret_value"})
    team = _team(
        staff,
        [
            {
                "service_id": "linear",
                "url": "https://linear.app/acme/team/BD",
                "external_id": "lin-bd",
            }
        ],
    )

    def graphql(body: dict[str, Any]) -> dict[str, Any]:
        assert body["variables"] == {"id": "lin-bd"}
        return {
            "data": {
                "team": {
                    "name": "Before Dawn",
                    "key": "BD",
                    "issues": {
                        "nodes": [
                            {
                                "identifier": "BD-3",
                                "title": "Deploy",
                                "url": "u3",
                                "updatedAt": "2026-11-21",
                                "state": {"name": "In Progress", "type": "started"},
                                "assignee": {"name": "Ana"},
                            },
                            {
                                "identifier": "BD-2",
                                "title": "Login",
                                "url": "u2",
                                "updatedAt": "2026-11-20",
                                "completedAt": "2026-11-20",
                                "state": {"name": "Done", "type": "completed"},
                                "assignee": None,
                            },
                            {
                                "identifier": "BD-1",
                                "title": "Setup",
                                "url": "u1",
                                "updatedAt": "2026-11-19",
                                "completedAt": "2026-11-19",
                                "state": {"name": "Done", "type": "completed"},
                            },
                        ]
                    },
                }
            }
        }

    fake_http.on("POST", "https://api.linear.app/graphql", graphql)
    r = staff.get(f"/api/tools/linear/teams/{team['id']}/updates")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["error"] is None
    assert body["counts"] == {"started": 1, "completed": 2}
    assert [i["identifier"] for i in body["issues"]] == ["BD-3", "BD-2", "BD-1"]
    assert body["issues"][0]["assignee"] == "Ana"


def test_linear_updates_explain_an_invisible_team(staff: TestClient, fake_http: FakeHttp) -> None:
    staff.put("/api/credentials/me/linear_api_key", json={"value": "lin_api_secret_value"})
    team = _team(staff, [])
    fake_http.on(
        "POST",
        "https://api.linear.app/graphql",
        {
            "data": {
                "organization": {"urlKey": "aiil"},
                "teams": {"nodes": [{"id": "x", "key": "RP", "name": "RepoPulse"}]},
            }
        },
    )
    body = staff.get(f"/api/tools/linear/teams/{team['id']}/updates").json()
    assert "Linear keys belong to one workspace" in body["error"]
    assert body["issues"] == []
