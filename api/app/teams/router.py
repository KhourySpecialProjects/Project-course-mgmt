"""HTTP endpoints under /api/teams (any logged-in user).

GET    /api/teams                                   all teams, with their links
GET    /api/teams/lookup?name=...                   what GitHub/Linear/... already have for a name
POST   /api/teams                                   create a team: {"name": "...", "links": [...]}
PATCH  /api/teams/{id}                              rename it
DELETE /api/teams/{id}                              delete it (nothing is deleted in GitHub etc.)

POST   /api/teams/{id}/links                        add a link (custom, or an existing repo/...)
PATCH  /api/teams/{id}/links/{link_id}              change its label or URL
DELETE /api/teams/{id}/links/{link_id}              remove it

GET    /api/teams/services                          services that put a button on team cards
POST   /api/teams/{id}/connect                      link whatever already exists ("Find links")
POST   /api/teams/{id}/services/{service_id}        create (or find) the team's repo/team/server
"""

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import CurrentUser, require_user
from app.core.db import DbSession
from app.modules import MODULES
from app.modules.base import ToolModule, status_for
from app.teams import service
from app.teams.models import Team
from app.teams.schemas import (
    TeamConnected,
    TeamCreate,
    TeamLinkCreate,
    TeamLinkUpdate,
    TeamLookup,
    TeamRead,
    TeamServiceCreated,
    TeamServiceInfo,
    TeamUpdate,
)
from app.teams.service import NewLink, TeamError

router = APIRouter(prefix="/teams", tags=["teams"], dependencies=[Depends(require_user)])


def _raise(err: TeamError) -> NoReturn:
    raise HTTPException(err.status_code, detail=err.message)


def _team(db: DbSession, team_id: int) -> Team:
    try:
        return service.get_team(db, team_id)
    except TeamError as err:
        _raise(err)


def team_service_modules() -> list[ToolModule]:
    """Tool modules that put a button on every team card, in registry order."""
    return [m for m in MODULES if m.team_service is not None]


def _service_module(service_id: str) -> ToolModule:
    module = next((m for m in team_service_modules() if m.id == service_id), None)
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown service: {service_id}")
    return module


def _new_link(body: TeamLinkCreate) -> NewLink:
    module = _service_module(body.service_id) if body.service_id is not None else None
    return NewLink(url=body.url, label=body.label, module=module, external_id=body.external_id)


# --- Services ---------------------------------------------------------------


@router.get("/services", response_model=list[TeamServiceInfo])
def list_services(user: CurrentUser, db: DbSession) -> list[TeamServiceInfo]:
    infos = []
    for m in team_service_modules():
        assert m.team_service is not None
        tool_status = status_for(m, db, user)
        infos.append(
            TeamServiceInfo(
                id=m.id,
                name=m.name,
                resource_name=m.team_service.resource_name,
                summary=m.team_service.summary,
                can_create=m.team_service.create is not None,
                configured=tool_status.configured,
                message=tool_status.message,
                missing_user_credentials=tool_status.missing_user_credentials,
                missing_system_credentials=tool_status.missing_system_credentials,
            )
        )
    return infos


@router.post("/{team_id}/connect", response_model=TeamConnected)
def connect(team_id: int, user: CurrentUser, db: DbSession) -> TeamConnected:
    """Link everything that already exists for the team in each service. Creates nothing."""
    team, results = service.connect(db, _team(db, team_id), user, team_service_modules())
    return TeamConnected(team=TeamRead.model_validate(team), results=results)


@router.post("/{team_id}/services/{service_id}", response_model=TeamServiceCreated)
def create_service_resource(
    team_id: int, service_id: str, user: CurrentUser, db: DbSession
) -> TeamServiceCreated:
    module = _service_module(service_id)
    assert module.team_service is not None
    try:
        team, created = service.create_service_resource(db, _team(db, team_id), module, user)
    except TeamError as err:
        _raise(err)
    verb = "Linked the existing" if created.already_existed else "Created the"
    return TeamServiceCreated(
        team=TeamRead.model_validate(team),
        message=f"{verb} {module.name} {module.team_service.resource_name} {created.label}.",
    )


# --- Teams ------------------------------------------------------------------


@router.get("", response_model=list[TeamRead])
def list_teams(db: DbSession) -> list[Team]:
    return service.list_teams(db)


@router.get("/lookup", response_model=TeamLookup)
def lookup(
    name: Annotated[str, Query(min_length=1, max_length=100)], user: CurrentUser, db: DbSession
) -> TeamLookup:
    """Search each service for an existing repo/team/project for a team called ``name``.

    Creates nothing. The "Add team" form calls this as the name is typed, to fill in
    the links it finds.
    """
    clean = " ".join(name.split())  # tidied the same way as when the team is saved
    if not clean:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Enter a team name")
    return service.lookup(db, user, clean, team_service_modules())


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(body: TeamCreate, user: CurrentUser, db: DbSession) -> Team:
    links = [_new_link(link) for link in body.links]
    try:
        return service.create_team(db, name=body.name, created_by=user, links=links)
    except TeamError as err:
        _raise(err)


@router.patch("/{team_id}", response_model=TeamRead)
def rename_team(team_id: int, body: TeamUpdate, db: DbSession) -> Team:
    try:
        return service.rename_team(db, _team(db, team_id), body.name)
    except TeamError as err:
        _raise(err)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(team_id: int, db: DbSession) -> None:
    service.delete_team(db, _team(db, team_id))


# --- Links ------------------------------------------------------------------


@router.post("/{team_id}/links", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def add_link(team_id: int, body: TeamLinkCreate, user: CurrentUser, db: DbSession) -> Team:
    link = _new_link(body)
    try:
        return service.add_link(db, _team(db, team_id), link, created_by=user)
    except TeamError as err:
        _raise(err)


@router.patch("/{team_id}/links/{link_id}", response_model=TeamRead)
def update_link(team_id: int, link_id: int, body: TeamLinkUpdate, db: DbSession) -> Team:
    team = _team(db, team_id)
    try:
        return service.update_link(
            db, team, service.get_link(team, link_id), label=body.label, url=body.url
        )
    except TeamError as err:
        _raise(err)


@router.delete("/{team_id}/links/{link_id}", response_model=TeamRead)
def delete_link(team_id: int, link_id: int, db: DbSession) -> Team:
    team = _team(db, team_id)
    try:
        return service.delete_link(db, team, service.get_link(team, link_id))
    except TeamError as err:
        _raise(err)
