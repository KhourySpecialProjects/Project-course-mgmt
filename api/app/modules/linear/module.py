"""Linear tool module.

Creates each team's Linear team from the dashboard's team cards (see
``team_service`` below). Inviting users, creating projects, and monitoring
progress will be added here.

Get the current user's key inside an endpoint with:

    from app.credentials.service import get_user_credential
    api_key = get_user_credential(db, user, "linear_api_key")
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, require_user
from app.core.db import DbSession
from app.core.http import ExternalServiceError
from app.credentials.service import get_user_credential
from app.credentials.spec import CredentialScope, CredentialSpec
from app.modules.base import CreatedResource, TeamService, ToolModule, ToolStatus, status_for
from app.modules.linear import client
from app.teams.models import Team
from app.users.models import User

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/status", response_model=ToolStatus)
def status(user: CurrentUser, db: DbSession) -> ToolStatus:
    """Report whether the Linear integration is ready for the current user."""
    return status_for(module, db, user)


# --- Team updates -------------------------------------------------------------------


class Issue(BaseModel):
    identifier: str
    title: str
    url: str
    updated_at: str
    completed_at: str | None = None
    state: str
    # backlog | unstarted | started | completed | canceled | triage
    state_type: str
    assignee: str | None = None


class LinearUpdates(BaseModel):
    # Why there's nothing to show (no Linear team linked, key can't see it, ...).
    error: str | None = None
    name: str | None = None
    key: str | None = None
    url: str | None = None
    counts: dict[str, int] = {}
    issues: list[Issue] = []


def team_updates(db: Session, user: User, team: Team) -> LinearUpdates:
    link = next((link for link in team.links if link.service_id == "linear"), None)
    api_key = get_user_credential(db, user, "linear_api_key")
    if api_key is None:
        return LinearUpdates(error="Add your Linear API key.")
    team_id = link.external_id if link else ""
    url = link.url if link else None
    try:
        if not team_id:
            found, _ = client.find_team(api_key, team.name)
            if found is None:
                return LinearUpdates(
                    error=(
                        f"No Linear team for {team.name} that your API key can see. Linear keys "
                        "belong to one workspace: make yours in the workspace the course uses, "
                        "and make sure you can see the team (it may be private)."
                    )
                )
            team_id, url = found.id, found.url
        data = client.team_activity(api_key, team_id)
    except ExternalServiceError as err:
        return LinearUpdates(error=str(err), url=url)
    return LinearUpdates.model_validate({**data, "url": url})


@router.get("/teams/{team_id}/updates", response_model=LinearUpdates)
def get_team_updates(team_id: int, user: CurrentUser, db: DbSession) -> LinearUpdates:
    """The team's recently updated Linear issues and its progress."""
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team_updates(db, user, team)


def _api_key(db: Session, user: User) -> str:
    api_key = get_user_credential(db, user, "linear_api_key")
    if api_key is None:
        raise ExternalServiceError("Linear isn't set up yet.")
    return api_key


def _resource(linear_team: client.LinearTeam, *, existed: bool) -> CreatedResource:
    return CreatedResource(
        url=linear_team.url,
        external_id=linear_team.id,
        label=f"{linear_team.name} ({linear_team.key})",
        already_existed=existed,
    )


def find_linear_team(db: Session, user: User, team_name: str) -> CreatedResource | None:
    """The Linear team with the workbench team's name, if there is one."""
    found, _ = client.find_team(_api_key(db, user), team_name)
    return _resource(found, existed=True) if found else None


def create_team_in_linear(db: Session, user: User, team: Team) -> CreatedResource:
    """Link the Linear team with the same name as the workbench team, creating it if needed."""
    api_key = _api_key(db, user)
    found, url_key = client.find_team(api_key, team.name)
    if found is not None:
        return _resource(found, existed=True)
    return _resource(client.create_team(api_key, team.name, url_key), existed=False)


module = ToolModule(
    id="linear",
    name="Linear",
    description="Invite users, create teams and projects, and monitor progress.",
    router=router,
    credentials=[
        CredentialSpec(
            key="linear_api_key",
            label="Linear personal API key",
            description=(
                "Lets the workbench act in Linear as you: inviting users and creating "
                "teams, projects, and issues. Create one in your Linear account settings."
            ),
            scope=CredentialScope.USER,
            placeholder="lin_api_...",
        ),
    ],
    team_service=TeamService(
        resource_name="team",
        summary=(
            "Creates a Linear team with the same name in your Linear workspace. If one "
            "with that name already exists, it's linked instead."
        ),
        create=create_team_in_linear,
        find=find_linear_team,
    ),
)
