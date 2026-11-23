"""The contract every tool module implements.

A *tool module* is a self-contained integration (GitHub, Linear, ...). The core
app knows nothing about any particular tool; it just loops over the registered
modules (see ``app/modules/__init__.py``) and mounts each one's router at
``/api/tools/<id>``.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.credentials.service import get_system_credential, get_user_credential
from app.credentials.spec import CredentialScope, CredentialSpec
from app.teams.models import Team
from app.users.models import User


@dataclass(frozen=True)
class CreatedResource:
    """What a ``TeamService.create`` function returns: the thing it made (or found) for a team."""

    # Where the button on the team's card should go, e.g. the repo's page on GitHub.
    url: str
    # The thing's stable id in the outside service, e.g. a GitHub repo id.
    external_id: str
    # Human-readable name for messages, e.g. "my-org/team-alpha".
    label: str
    # True if it already existed (e.g. a repo with the team's name) and was linked, not created.
    already_existed: bool = False


@dataclass(frozen=True)
class TeamService:
    """Lets a tool module create something for each team, shown as a button on the team's card.

    Set ``ToolModule(team_service=TeamService(...))`` and every team card on the
    dashboard gets a button for the module. Clicking it when the team has no link
    yet calls ``create``; afterwards the button opens the link.
    """

    # What it links to, in lower case: "repository", "team", "server".
    resource_name: str
    # One or two sentences shown before creating/finding, e.g. what it will be called.
    summary: str
    # Makes (or finds) the thing for the team. Runs only once the module is configured
    # for the user. Raise ``app.core.http.ExternalServiceError`` with a helpful
    # message if the outside service refuses. Leave out for things the workbench
    # should only find, never make (e.g. servers, which cost money).
    create: Callable[[Session, User, Team], CreatedResource] | None = None
    # Look for an existing one for a team called <name>, without creating anything;
    # None if there isn't one. Fills in the "Add team" form as the name is typed, and
    # powers a card's "Find links". Same rules as ``create`` for errors.
    find: Callable[[Session, User, str], CreatedResource | None] | None = None

    def __post_init__(self) -> None:
        if self.create is None and self.find is None:
            raise ValueError("A TeamService needs a create function, a find function, or both")


@dataclass(frozen=True)
class ToolModule:
    # Short, URL-safe identifier, e.g. "github". Used in URLs and must match the
    # id of the matching module in the web app (web/src/modules).
    id: str
    name: str
    description: str
    router: APIRouter
    # API keys / tokens this module needs. They appear automatically on the
    # Account page (scope USER) and in System settings (SYSTEM keys, plus a
    # superuser's own USER keys).
    credentials: list[CredentialSpec] = field(default_factory=list)
    # Optional: a button on each team's card that creates the team's repo/project/...
    team_service: TeamService | None = None

    def missing_credentials(self, db: Session, user: User) -> list[CredentialSpec]:
        """The credentials still needed before ``user`` can use this module."""
        missing = []
        for spec in self.credentials:
            if spec.scope == CredentialScope.TEAM or not spec.required:
                continue  # set per team (checked where a team is involved), or optional
            if spec.scope == CredentialScope.USER:
                value = get_user_credential(db, user, spec.key)
            else:
                value = get_system_credential(db, spec.key)
            if value is None:
                missing.append(spec)
        return missing

    def is_configured(self, db: Session, user: User) -> bool:
        return not self.missing_credentials(db, user)


class ToolInfo(BaseModel):
    """What ``GET /api/tools`` returns for each module."""

    id: str
    name: str
    description: str
    configured: bool


class CredentialRef(BaseModel):
    """One API key a module uses (the value itself is never included)."""

    key: str
    label: str
    scope: CredentialScope
    required: bool


class ToolStatus(BaseModel):
    """What each module's ``GET /api/tools/<id>/status`` returns."""

    configured: bool
    message: str
    # Keys of credentials still to be added, and where they're managed.
    missing_user_credentials: list[str] = []
    missing_system_credentials: list[str] = []
    # Every personal and shared key the module uses, so its page can offer to change them.
    credentials: list[CredentialRef] = []


def _join_labels(specs: list[CredentialSpec]) -> str:
    """'A', 'A and B', or 'A, B, and C'."""
    labels = [s.label for s in specs]
    if len(labels) <= 2:
        return " and ".join(labels)
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def status_for(module: ToolModule, db: Session, user: User) -> ToolStatus:
    """A ready-made status response that any module can return from its /status endpoint."""
    missing = module.missing_credentials(db, user)
    refs = [
        CredentialRef(key=s.key, label=s.label, scope=s.scope, required=s.required)
        for s in module.credentials
        if s.scope != CredentialScope.TEAM
    ]
    if not missing:
        return ToolStatus(
            configured=True, message=f"{module.name} is ready to use.", credentials=refs
        )

    user_missing = [s for s in missing if s.scope == CredentialScope.USER]
    system_missing = [s for s in missing if s.scope == CredentialScope.SYSTEM]
    if user.is_superuser:
        # Superusers manage every key, their own and the shared ones, in System settings.
        message = f"Add the {_join_labels(missing)} in System settings."
    else:
        parts = []
        if user_missing:
            parts.append(
                f"Add your {_join_labels(user_missing)} on your Account page (API keys tab)."
            )
        if system_missing:
            names = _join_labels(system_missing)
            parts.append(f"An administrator needs to add the {names} in System settings.")
        message = " ".join(parts)
    return ToolStatus(
        configured=False,
        message=message,
        missing_user_credentials=[s.key for s in user_missing],
        missing_system_credentials=[s.key for s in system_missing],
        credentials=refs,
    )
