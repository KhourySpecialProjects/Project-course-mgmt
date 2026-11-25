"""Business logic for teams and their links.

The interesting part is ``create_service_resource``: it asks a tool module
(GitHub, Linear, Coolify, ...) to make the team's repo/team/project and saves
the link to it.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.http import ExternalServiceError
from app.modules.base import CreatedResource, ToolModule, status_for
from app.teams.models import Team, TeamLink, TeamMember
from app.teams.schemas import (
    ConnectOutcome,
    ConnectResult,
    FoundResource,
    ServiceLookup,
    TeamLookup,
    TeamMemberWrite,
    parse_member_line,
)
from app.users.models import User


class TeamError(Exception):
    """Something the user asked for can't be done. ``message`` is shown to them."""

    def __init__(self, message: str, *, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _name_taken(name: str) -> TeamError:
    return TeamError(f"There's already a team called {name}.", status_code=status.HTTP_409_CONFLICT)


# --- Teams ------------------------------------------------------------------


def list_teams(db: Session) -> list[Team]:
    return list(db.scalars(select(Team).order_by(func.lower(Team.name), Team.id)))


def get_team(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise TeamError("Team not found", status_code=status.HTTP_404_NOT_FOUND)
    return team


def _check_name_free(db: Session, name: str, *, except_id: int | None = None) -> None:
    query = select(Team.id).where(func.lower(Team.name) == name.lower())
    if except_id is not None:
        query = query.where(Team.id != except_id)
    if db.scalar(query) is not None:
        raise _name_taken(name)


def _commit_name(db: Session, name: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        # Someone else took the name between our check and the commit.
        db.rollback()
        raise _name_taken(name) from None


@dataclass(frozen=True)
class NewLink:
    url: str
    label: str = ""
    # The built-in service it's for (GitHub, ...), or None for a custom link.
    module: ToolModule | None = None
    # The thing's id in that service, when known (from ``lookup``).
    external_id: str = ""


def create_team(
    db: Session,
    *,
    name: str,
    created_by: User,
    links: Sequence[NewLink] = (),
    members: Sequence[TeamMemberWrite] = (),
) -> Team:
    """Create a team, with all its links and students in one go (or none)."""
    _check_name_free(db, name)
    team = Team(name=name, created_by_id=created_by.id, links=[], members=[])
    for link in links:
        team.links.append(_new_link(db, team, link, created_by))
    for m in members:
        if _duplicate(team, m) is None:
            team.members.append(TeamMember(**m.model_dump()))
    db.add(team)
    _commit_name(db, name)
    return team


# --- Students -----------------------------------------------------------------


def _duplicate(team: Team, m: TeamMemberWrite, *, except_id: int | None = None) -> str | None:
    """Why ``m`` is already on the team (same email or GitHub username), if it is."""
    for other in team.members:
        if other.id is not None and other.id == except_id:
            continue
        if m.email and other.email.lower() == m.email.lower():
            return f"{other.name} already has the email {m.email}."
        if m.github_username and other.github_username.lower() == m.github_username.lower():
            return f"{other.name} already has the GitHub username {m.github_username}."
    return None


def get_member(team: Team, member_id: int) -> TeamMember:
    member = next((m for m in team.members if m.id == member_id), None)
    if member is None:
        raise TeamError("Student not found", status_code=status.HTTP_404_NOT_FOUND)
    return member


def add_member(db: Session, team: Team, m: TeamMemberWrite) -> Team:
    why = _duplicate(team, m)
    if why:
        raise TeamError(why, status_code=status.HTTP_409_CONFLICT)
    team.members.append(TeamMember(**m.model_dump()))
    db.commit()
    db.refresh(team, ["members"])
    return team


def update_member(db: Session, team: Team, member: TeamMember, m: TeamMemberWrite) -> Team:
    why = _duplicate(team, m, except_id=member.id)
    if why:
        raise TeamError(why, status_code=status.HTTP_409_CONFLICT)
    for key, value in m.model_dump().items():
        setattr(member, key, value)
    db.commit()
    db.refresh(team, ["members"])
    return team


def delete_member(db: Session, team: Team, member: TeamMember) -> Team:
    team.members.remove(member)
    db.commit()
    return team


def paste_members(db: Session, team: Team, text: str) -> tuple[Team, int, list[str]]:
    """Add one student per line. Returns the team, how many were added, and what was skipped."""
    added, skipped = 0, []
    for line in text.splitlines():
        try:
            m = parse_member_line(line)
        except ValueError as err:
            skipped.append(f"{line.strip()}: {_first_error(err)}")
            continue
        if m is None:
            continue
        why = _duplicate(team, m)
        if why:
            skipped.append(f"{line.strip()}: {why}")
            continue
        team.members.append(TeamMember(**m.model_dump()))
        db.flush()  # so the next line's duplicate check sees this one
        added += 1
    db.commit()
    db.refresh(team, ["members"])
    return team, added, skipped


def _first_error(err: ValueError) -> str:
    errors = getattr(err, "errors", None)
    if callable(errors):
        items = errors()
        if items:
            return str(items[0].get("msg", err)).removeprefix("Value error, ")
    return str(err)


def rename_team(db: Session, team: Team, name: str) -> Team:
    _check_name_free(db, name, except_id=team.id)
    team.name = name
    _commit_name(db, name)
    return team


def delete_team(db: Session, team: Team) -> None:
    """Remove the team and its links. Nothing is deleted in GitHub, Linear, etc."""
    db.delete(team)
    db.commit()


# --- Links ------------------------------------------------------------------


def get_link(team: Team, link_id: int) -> TeamLink:
    link = next((link for link in team.links if link.id == link_id), None)
    if link is None:
        raise TeamError("Link not found", status_code=status.HTTP_404_NOT_FOUND)
    return link


def _service_link(team: Team, service_id: str) -> TeamLink | None:
    return next((link for link in team.links if link.service_id == service_id), None)


def _already_has(team: Team, module: ToolModule) -> TeamError:
    resource = module.team_service.resource_name if module.team_service else "link"
    return TeamError(
        f"{team.name} already has a {module.name} {resource}.",
        status_code=status.HTTP_409_CONFLICT,
    )


def linked_team(
    db: Session, service_id: str, external_id: str, *, except_team_id: int | None = None
) -> Team | None:
    """The team already linked to this repo/team/project, if any."""
    if not external_id:
        return None
    query = (
        select(Team)
        .join(TeamLink)
        .where(TeamLink.service_id == service_id, TeamLink.external_id == external_id)
    )
    if except_team_id is not None:
        query = query.where(Team.id != except_team_id)
    return db.scalar(query)


def _taken_by(module: ToolModule, label: str, owner: Team) -> TeamError:
    resource = module.team_service.resource_name if module.team_service else "link"
    return TeamError(
        f"The {module.name} {resource} {label} is already linked to {owner.name}.",
        status_code=status.HTTP_409_CONFLICT,
    )


def _new_link(db: Session, team: Team, link: NewLink, created_by: User) -> TeamLink:
    module = link.module
    if module is not None:
        if _service_link(team, module.id) is not None:
            raise _already_has(team, module)
        owner = linked_team(db, module.id, link.external_id, except_team_id=team.id)
        if owner is not None:
            raise _taken_by(module, link.url, owner)
    return TeamLink(
        service_id=module.id if module else None,
        # A built-in service's link is labelled with what it points to (e.g. the repo's
        # full name, from the lookup), or else the service's name.
        label=(link.label or module.name) if module else link.label,
        url=link.url,
        external_id=link.external_id if module else "",
        created_by_id=created_by.id,
    )


def add_link(db: Session, team: Team, link: NewLink, *, created_by: User) -> Team:
    """Add a custom link, or (with ``module``) link an existing repo/team/project by its URL."""
    team.links.append(_new_link(db, team, link, created_by))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if link.module is None:
            raise
        raise _already_has(team, link.module) from None
    return team


def update_link(
    db: Session, team: Team, link: TeamLink, *, label: str | None, url: str | None
) -> Team:
    if label is not None:
        link.label = label
    if url is not None and url != link.url:
        link.url = url
        link.external_id = ""  # it may point somewhere else now
    db.commit()
    return team


def delete_link(db: Session, team: Team, link: TeamLink) -> Team:
    """Remove the link only. The repo/team/project it points to is left alone."""
    team.links.remove(link)
    db.commit()
    return team


# --- Looking up what already exists -------------------------------------------


def lookup(db: Session, user: User, name: str, modules: Sequence[ToolModule]) -> TeamLookup:
    """What each service already has for a team called ``name``. Creates nothing.

    Each service is asked separately, so one failing (or not being set up) doesn't
    stop the others from filling in.
    """
    taken = db.scalar(select(Team.id).where(func.lower(Team.name) == name.lower()))
    results = []
    for module in modules:
        service = module.team_service
        tool_status = status_for(module, db, user)
        result = ServiceLookup(service_id=module.id, configured=tool_status.configured)
        if not tool_status.configured:
            result.error = tool_status.message
        elif service is not None and service.find is not None:
            try:
                found = service.find(db, user, name)
            except ExternalServiceError as err:
                result.error = str(err)
            else:
                if found is not None:
                    result.found = FoundResource(
                        url=found.url, label=found.label, external_id=found.external_id
                    )
                    owner = linked_team(db, module.id, found.external_id)
                    result.linked_team = owner.name if owner else None
        results.append(result)
    return TeamLookup(name=name, name_taken=taken is not None, services=results)


def connect(
    db: Session, team: Team, user: User, modules: Sequence[ToolModule]
) -> tuple[Team, list[ConnectResult]]:
    """Link everything that already exists for the team. Creates nothing.

    For each service the team has no link for yet, look for its repo/team/server
    (see ``lookup``) and link it if found and not some other team's.
    """
    results = [
        _connect_one(db, team, user, m)
        for m in modules
        if m.team_service is not None and m.team_service.find is not None
    ]
    db.commit()
    return team, results


def _connect_one(db: Session, team: Team, user: User, module: ToolModule) -> ConnectResult:
    service = module.team_service
    assert service is not None and service.find is not None
    what = f"{module.name} {service.resource_name}"

    def result(outcome: ConnectOutcome, message: str) -> ConnectResult:
        return ConnectResult(service_id=module.id, outcome=outcome, message=message)

    if _service_link(team, module.id) is not None:
        return result("already_linked", f"Already linked to its {what}.")
    tool_status = status_for(module, db, user)
    if not tool_status.configured:
        return result("not_set_up", tool_status.message)
    try:
        found = service.find(db, user, team.name)
    except ExternalServiceError as err:
        return result("error", str(err))
    if found is None:
        return result("not_found", f"No {what} found for {team.name}.")
    owner = linked_team(db, module.id, found.external_id, except_team_id=team.id)
    if owner is not None:
        return result("taken", f"Found {found.label}, but it's already linked to {owner.name}.")
    team.links.append(
        TeamLink(
            service_id=module.id,
            label=found.label[:100],
            url=found.url,
            external_id=found.external_id,
            created_by_id=user.id,
        )
    )
    return result("linked", f"Linked {found.label}.")


# --- Creating things in outside services --------------------------------------


def create_service_resource(
    db: Session, team: Team, module: ToolModule, user: User
) -> tuple[Team, CreatedResource]:
    """Have ``module`` create (or find) the team's repo/team/project, and link it to the team."""
    service = module.team_service
    if service is None:
        raise TeamError(f"{module.name} can't create things for teams.")

    # Lock the team's row until we commit, so two people clicking at the same
    # time can't both create a repository.
    db.scalar(select(Team.id).where(Team.id == team.id).with_for_update())
    db.refresh(team, ["links"])
    if _service_link(team, module.id) is not None:
        db.rollback()
        raise _already_has(team, module)

    tool_status = status_for(module, db, user)
    if not tool_status.configured:
        db.rollback()
        raise TeamError(tool_status.message)

    try:
        if service.create is not None:
            created = service.create(db, user, team)
        else:
            assert service.find is not None  # TeamService guarantees one of the two
            found = service.find(db, user, team.name)
            if found is None:
                db.rollback()
                raise TeamError(
                    f"No {module.name} {service.resource_name} found for {team.name}. "
                    f"{service.summary}",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            created = found
    except ExternalServiceError as err:
        db.rollback()
        raise TeamError(str(err), status_code=status.HTTP_502_BAD_GATEWAY) from None

    # If it already existed, make sure it isn't some other team's.
    owner = linked_team(db, module.id, created.external_id, except_team_id=team.id)
    if owner is not None:
        db.rollback()
        raise _taken_by(module, created.label, owner)

    team.links.append(
        TeamLink(
            service_id=module.id,
            label=created.label[:100],
            url=created.url,
            external_id=created.external_id,
            created_by_id=user.id,
        )
    )
    db.commit()
    return team, created
