"""Students on teams: adding them one at a time, pasting a list, and with a new team."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.teams.schemas import parse_member_line


def _team(client: TestClient, **extra: Any) -> dict[str, Any]:
    r = client.post("/api/teams", json={"name": "Before Dawn", **extra})
    assert r.status_code == 201, r.text
    team: dict[str, Any] = r.json()
    return team


def test_students_can_be_added_changed_and_removed(staff: TestClient) -> None:
    team = _team(staff)
    url = f"/api/teams/{team['id']}/members"

    r = staff.post(
        url,
        json={"name": "  Ana   Diaz ", "email": "Ana@School.EDU", "github_username": "@anadiaz"},
    )
    assert r.status_code == 201, r.text
    [ana] = r.json()["members"]
    assert (ana["name"], ana["email"], ana["github_username"]) == (
        "Ana Diaz",
        "ana@school.edu",
        "anadiaz",
    )

    # The same email or GitHub username can't be on the team twice.
    assert staff.post(url, json={"name": "Other", "email": "ana@school.edu"}).status_code == 409
    assert staff.post(url, json={"name": "Other", "github_username": "ANADIAZ"}).status_code == 409
    assert staff.post(url, json={"name": "Bad", "email": "not-an-email"}).status_code == 422
    assert staff.post(url, json={"name": "Bad", "github_username": "no spaces"}).status_code == 422

    r = staff.patch(
        f"{url}/{ana['id']}",
        json={"name": "Ana Diaz", "role": "PM", "github_username": "https://github.com/ana-d"},
    )
    assert r.status_code == 200, r.text
    assert (r.json()["members"][0]["role"], r.json()["members"][0]["github_username"]) == (
        "PM",
        "ana-d",
    )

    # Students come with the team everywhere it's listed.
    assert staff.get("/api/teams").json()[0]["members"][0]["name"] == "Ana Diaz"

    assert staff.delete(f"{url}/{ana['id']}").json()["members"] == []
    assert staff.delete(f"{url}/{ana['id']}").status_code == 404


def test_pasting_a_list_of_students(staff: TestClient) -> None:
    team = _team(staff, members=[{"name": "Ana Diaz", "email": "ana@school.edu"}])
    text = "\n".join(
        [
            "Ben Ito, ben@school.edu, @benito, Tech lead",
            "",
            "@cara-k\tCara Kim\tcara@school.edu",  # tabs (from a spreadsheet), any order
            "Ana Again; ana@school.edu",  # already on the team
            "dee@school.edu",  # just an email: the name comes from it
            "Bad Person, @not valid",
        ]
    )
    r = staff.post(f"/api/teams/{team['id']}/members/paste", json={"text": text})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["added"] == 3
    names = {m["name"]: m for m in body["team"]["members"]}
    assert set(names) == {"Ana Diaz", "Ben Ito", "Cara Kim", "dee"}
    assert (names["Ben Ito"]["github_username"], names["Ben Ito"]["role"]) == (
        "benito",
        "Tech lead",
    )
    assert names["Cara Kim"]["github_username"] == "cara-k"
    assert len(body["skipped"]) == 2
    assert "already has the email" in body["skipped"][0]
    assert "isn't a GitHub username" in body["skipped"][1]


def test_deleting_a_team_deletes_its_students(staff: TestClient) -> None:
    team = _team(staff, members=[{"name": "Ana Diaz"}])
    assert staff.delete(f"/api/teams/{team['id']}").status_code == 204
    assert _team(staff)["members"] == []


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Ana Diaz, ana@school.edu, @anadiaz, PM", ("Ana Diaz", "ana@school.edu", "anadiaz", "PM")),
        ("ana@school.edu", ("ana", "ana@school.edu", "", "")),
        ("https://github.com/octocat", ("octocat", "", "octocat", "")),
        ("Just A Name", ("Just A Name", "", "", "")),
        # A spreadsheet's columns: the third is the GitHub username, even without an @.
        (
            "Ben Ito	ben@school.edu	benito	Tech lead",
            ("Ben Ito", "ben@school.edu", "benito", "Tech lead"),
        ),
        # An empty GitHub column keeps the role a role.
        ("Ana Diaz, ana@school.edu, , PM", ("Ana Diaz", "ana@school.edu", "", "PM")),
        ("@cara-k	Cara Kim	cara@school.edu", ("Cara Kim", "cara@school.edu", "cara-k", "")),
    ],
)
def test_parse_member_line(line: str, expected: tuple[str, str, str, str]) -> None:
    m = parse_member_line(line)
    assert m is not None
    assert (m.name, m.email, m.github_username, m.role) == expected
    assert parse_member_line("   ") is None
