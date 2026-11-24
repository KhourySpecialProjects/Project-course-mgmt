"""GitHub tool module.

Creates each team's repository from the dashboard's team cards (see
``team_service`` below). Bulk repo creation, teams, and permissions will be
added here.

Get the current user's token and the course organization inside an endpoint with:

    from app.credentials.service import get_system_credential, get_user_credential
    token = get_user_credential(db, user, "github_token")
    org = get_system_credential(db, "github_org")
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, require_user
from app.core.db import DbSession
from app.core.http import ExternalServiceError
from app.core.naming import best_match, slugify
from app.credentials.service import get_system_credential, get_user_credential
from app.credentials.spec import CredentialScope, CredentialSpec
from app.modules.base import CreatedResource, TeamService, ToolModule, ToolStatus, status_for
from app.modules.github import client
from app.teams.models import Team
from app.users.models import User

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/status", response_model=ToolStatus)
def status(user: CurrentUser, db: DbSession) -> ToolStatus:
    """Report whether the GitHub integration is ready for the current user."""
    return status_for(module, db, user)


# --- Team updates -------------------------------------------------------------------


class Commit(BaseModel):
    sha: str
    message: str
    author: str
    date: str
    url: str


class Pull(BaseModel):
    number: int | None
    title: str
    author: str
    state: str
    draft: bool
    updated_at: str
    url: str


class RepoUpdates(BaseModel):
    full_name: str
    # Why it's listed: "Linked on the team card" or "Coolify deploys dev, main".
    source: str
    error: str | None = None
    url: str | None = None
    private: bool | None = None
    branch: str | None = None
    pushed_at: str | None = None
    open_issues: int = 0
    commits: list[Commit] = []
    open_pulls: list[Pull] = []
    recent_merged: list[Pull] = []


def _team_repos(db: Session, team: Team) -> dict[str, str]:
    """owner/name -> why it's included: the card's GitHub link, then Coolify's deploy repos."""
    repos: dict[str, str] = {}
    link = next((link for link in team.links if link.service_id == "github"), None)
    if link and "github.com/" in link.url:
        full = link.url.split("github.com/", 1)[1].strip("/").removesuffix(".git")
        if full.count("/") == 1:
            repos[full] = "Linked on the team card"
    from app.modules.coolify.service import deployed_repos

    for full, branches in deployed_repos(db, team).items():
        why = f"Coolify deploys {', '.join(branches)}" if branches else "Deployed by Coolify"
        key = next((r for r in repos if r.lower() == full.lower()), full)
        repos[key] = f"{repos[key]}; {why}" if key in repos else why
    return repos


def team_updates(db: Session, user: User, team: Team) -> list[RepoUpdates]:
    token = get_user_credential(db, user, "github_token")
    out = []
    for full, source in _team_repos(db, team).items():
        if token is None:
            out.append(RepoUpdates(full_name=full, source=source, error="Add your GitHub token."))
            continue
        try:
            data = client.repo_activity(token, full)
        except ExternalServiceError as err:
            out.append(RepoUpdates(full_name=full, source=source, error=str(err)))
            continue
        out.append(RepoUpdates.model_validate({**data, "source": source}))
    return out


@router.get("/teams/{team_id}/updates", response_model=list[RepoUpdates])
def get_team_updates(team_id: int, user: CurrentUser, db: DbSession) -> list[RepoUpdates]:
    """Recent commits and pull requests in the team's repositories."""
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team_updates(db, user, team)


def repo_name(team_name: str) -> str:
    """The team's repository name: "Team Alpha" -> "team-alpha" (empty if no letters/digits)."""
    return slugify(team_name)[:100]


def org_name(value: str) -> str:
    """Accept "my-org" as well as a pasted "https://github.com/my-org/"."""
    return value.strip().rstrip("/").rsplit("/", 1)[-1]


def _settings(db: Session, user: User) -> tuple[str, str]:
    token = get_user_credential(db, user, "github_token")
    org = get_system_credential(db, "github_org")
    if token is None or org is None:
        raise ExternalServiceError("GitHub isn't set up yet.")
    return token, org_name(org)


def _resource(repo: dict[str, Any], *, existed: bool) -> CreatedResource:
    return CreatedResource(
        url=str(repo["html_url"]),
        external_id=str(repo["id"]),
        label=str(repo["full_name"]),
        already_existed=existed,
    )


def find_team_repo(db: Session, user: User, team_name: str) -> CreatedResource | None:
    """The org's repository for the team, if there is one.

    First the exact name ("Team Alpha" -> team-alpha), then any repo whose name matches
    or contains the team's ("Before Dawn" -> BeforeDawnArchitecturePatterns).
    """
    token, org = _settings(db, user)
    name = repo_name(team_name)
    repo = client.get_repo(token, org, name) if name else None
    if repo is None:
        repos = client.list_org_repos(token, org)
        repo = best_match(team_name, repos, names=lambda r: [str(r.get("name", ""))])
    return _resource(repo, existed=True) if repo else None


def create_team_repo(db: Session, user: User, team: Team) -> CreatedResource:
    """Link the org's repository named after the team, creating it if it doesn't exist."""
    found = find_team_repo(db, user, team.name)
    if found is not None:
        return found
    token, org = _settings(db, user)
    name = repo_name(team.name) or f"team-{team.id}"
    repo = client.create_org_repo(token, org, name, description=f"{team.name} team project")
    return _resource({"full_name": f"{org}/{name}", **repo}, existed=False)


module = ToolModule(
    id="github",
    name="GitHub",
    description="Create repos and teams in bulk, manage access, and view the org.",
    router=router,
    credentials=[
        CredentialSpec(
            key="github_token",
            label="GitHub personal access token",
            description=(
                "Lets the workbench act in GitHub as you: creating repos and teams and "
                "managing access in your course organization. Needs admin rights on the org."
            ),
            scope=CredentialScope.USER,
            help_url="https://github.com/settings/tokens",
            placeholder="github_pat_...",
        ),
        CredentialSpec(
            key="github_org",
            label="GitHub organization",
            description=(
                "The course's GitHub organization, where team repositories are created. "
                "Just its name, e.g. cs4530-fall26 for github.com/cs4530-fall26."
            ),
            scope=CredentialScope.SYSTEM,
            placeholder="my-course-org",
        ),
    ],
    team_service=TeamService(
        resource_name="repository",
        summary=(
            "Creates a private repository named after the team in the course's GitHub "
            "organization (Team Alpha becomes team-alpha). If the organization already has "
            "the team's repository (e.g. BeforeDawnArchitecturePatterns for Before Dawn), "
            "it's linked instead."
        ),
        create=create_team_repo,
        find=find_team_repo,
    ),
)
