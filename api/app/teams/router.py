"""HTTP endpoints under /api/teams (any logged-in user).

GET    /api/teams                                   all teams, with their links
GET    /api/teams/lookup?name=...                   what GitHub/Linear/... already have for a name
POST   /api/teams                                   create a team: {"name": "...", "links": [...]}
PATCH  /api/teams/{id}                              rename it
DELETE /api/teams/{id}                              delete it (nothing is deleted in GitHub etc.)

POST   /api/teams/{id}/links                        add a link (custom, or an existing repo/...)
PATCH  /api/teams/{id}/links/{link_id}              change its label or URL
DELETE /api/teams/{id}/links/{link_id}              remove it

GET    /api/teams/{id}/credentials                  the team's own API keys (never their values)
PUT    /api/teams/{id}/credentials/{key}            save one: {"value": "..."}
DELETE /api/teams/{id}/credentials/{key}            remove one

GET    /api/teams/services                          services that put a button on team cards
POST   /api/teams/{id}/connect                      link whatever already exists ("Find links")
POST   /api/teams/{id}/services/{service_id}        create (or find) the team's repo/team/server
"""

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth.dependencies import CurrentUser, require_user
from app.core.db import DbSession
from app.credentials import registry
from app.credentials.schemas import CredentialStatus, CredentialUpdate
from app.credentials.spec import CredentialScope, CredentialSpec
from app.modules import MODULES
from app.modules.base import ToolModule, status_for
from app.teams import credentials as team_credentials
from app.teams import service
from app.teams.models import Team, TeamCredential
from app.teams.schemas import (
    TeamConnected,
    TeamCreate,
    TeamLinkCreate,
    TeamLinkUpdate,
    TeamLookup,
    TeamMembersPaste,
    TeamMemberWrite,
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
        return service.create_team(
            db, name=body.name, created_by=user, links=links, members=body.members
        )
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


# --- Students ---------------------------------------------------------------


class PasteResult(BaseModel):
    team: TeamRead
    added: int
    # Lines that weren't added, with the reason.
    skipped: list[str]


@router.post("/{team_id}/members", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def add_member(team_id: int, body: TeamMemberWrite, db: DbSession) -> Team:
    try:
        return service.add_member(db, _team(db, team_id), body)
    except TeamError as err:
        _raise(err)


@router.post("/{team_id}/members/paste", response_model=PasteResult)
def paste_members(team_id: int, body: TeamMembersPaste, db: DbSession) -> PasteResult:
    """Add several students at once, one per line: "Name, email, @github, role"."""
    team, added, skipped = service.paste_members(db, _team(db, team_id), body.text)
    return PasteResult(team=TeamRead.model_validate(team), added=added, skipped=skipped)


@router.patch("/{team_id}/members/{member_id}", response_model=TeamRead)
def update_member(team_id: int, member_id: int, body: TeamMemberWrite, db: DbSession) -> Team:
    team = _team(db, team_id)
    try:
        return service.update_member(db, team, service.get_member(team, member_id), body)
    except TeamError as err:
        _raise(err)


@router.delete("/{team_id}/members/{member_id}", response_model=TeamRead)
def delete_member(team_id: int, member_id: int, db: DbSession) -> Team:
    team = _team(db, team_id)
    try:
        return service.delete_member(db, team, service.get_member(team, member_id))
    except TeamError as err:
        _raise(err)


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


# --- Team API keys ----------------------------------------------------------


def _team_specs() -> list[CredentialSpec]:
    return [s for s in registry.specs_for(CredentialScope.TEAM)]


def _team_spec(key: str) -> CredentialSpec:
    spec = next((s for s in _team_specs() if s.key == key), None)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown team credential: {key}")
    return spec


def _cred_status(spec: CredentialSpec, cred: TeamCredential | None) -> CredentialStatus:
    return CredentialStatus(
        key=spec.key,
        label=spec.label,
        description=spec.description,
        scope=spec.scope,
        help_url=spec.help_url,
        placeholder=spec.placeholder,
        is_set=cred is not None,
        hint=cred.hint if cred else "",
        readable=team_credentials.is_readable(cred) if cred else True,
        updated_at=cred.updated_at if cred else None,
    )


@router.get("/{team_id}/credentials", response_model=list[CredentialStatus])
def list_team_credentials(team_id: int, db: DbSession) -> list[CredentialStatus]:
    """The team's own API keys (e.g. its Coolify token). Values are never returned."""
    team = _team(db, team_id)
    saved = team_credentials.list_saved(db, team.id)
    return [_cred_status(spec, saved.get(spec.key)) for spec in _team_specs()]


@router.put("/{team_id}/credentials/{key}", response_model=CredentialStatus)
def set_team_credential(
    team_id: int, key: str, body: CredentialUpdate, user: CurrentUser, db: DbSession
) -> CredentialStatus:
    team = _team(db, team_id)
    spec = _team_spec(key)
    cred = team_credentials.save(db, team_id=team.id, key=key, value=body.value, updated_by=user)
    return _cred_status(spec, cred)


@router.delete("/{team_id}/credentials/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_credential(team_id: int, key: str, db: DbSession) -> None:
    team = _team(db, team_id)
    _team_spec(key)
    team_credentials.delete(db, team_id=team.id, key=key)
