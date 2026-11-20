from datetime import datetime
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _clean_text(value: str) -> str:
    value = " ".join(value.split())  # trim, and collapse runs of spaces
    if not value:
        raise ValueError("Cannot be blank")
    return value


def _clean_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("Enter a full web address starting with https://")
    return value


class TeamLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # The tool module this link belongs to ("github", ...), or None for a custom link.
    service_id: str | None
    label: str
    url: str
    created_at: datetime


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    links: list[TeamLinkRead]
    created_at: datetime


class TeamName(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        return _clean_text(v)


class TeamUpdate(TeamName):
    pass


class TeamLinkCreate(BaseModel):
    """A link added by hand: a custom one (label + url), or an existing repo/team/project
    for one of the built-in services (service_id + url)."""

    url: str = Field(min_length=1, max_length=2000)
    label: str = Field(default="", max_length=100)
    service_id: str | None = None
    # The thing's id in the service, when it came from GET /api/teams/lookup. Lets the
    # workbench stop two teams from being linked to the same repo/team/project.
    external_id: str = Field(default="", max_length=200)

    @field_validator("url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        return _clean_url(v)

    @field_validator("label")
    @classmethod
    def _strip_label(cls, v: str) -> str:
        return " ".join(v.split())

    @model_validator(mode="after")
    def _custom_links_need_a_label(self) -> Self:
        if self.service_id is None and not self.label:
            raise ValueError("Give the link a name, e.g. Figma or Slack")
        return self


class TeamCreate(TeamName):
    """A new team, optionally with its links (all of them at once, from the "Add team" form)."""

    links: list[TeamLinkCreate] = Field(default=[], max_length=50)

    @model_validator(mode="after")
    def _one_link_per_service(self) -> Self:
        ids = [link.service_id for link in self.links if link.service_id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("A team can have only one link per service")
        return self


class TeamLinkUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    url: str | None = Field(default=None, min_length=1, max_length=2000)

    @field_validator("label")
    @classmethod
    def _clean_label(cls, v: str | None) -> str | None:
        return None if v is None else _clean_text(v)

    @field_validator("url")
    @classmethod
    def _check_url(cls, v: str | None) -> str | None:
        return None if v is None else _clean_url(v)


class TeamServiceInfo(BaseModel):
    """A built-in service that can create something for each team (GitHub, Linear, ...)."""

    id: str
    name: str
    # What it links to: "repository", "team", "server".
    resource_name: str
    summary: str
    # False for services that only find things (e.g. a team's server), never make them.
    can_create: bool = True
    # Whether the current user has everything set up to use it, and if not, what's missing.
    configured: bool
    message: str
    missing_user_credentials: list[str] = []
    missing_system_credentials: list[str] = []


class FoundResource(BaseModel):
    url: str
    label: str
    external_id: str


class ServiceLookup(BaseModel):
    """What one service has for a team name, for filling in the "Add team" form."""

    service_id: str
    # Whether the current user has the keys to search (and create) in this service.
    configured: bool
    # The existing repo/team/project for this name, if any.
    found: FoundResource | None = None
    # Name of the workbench team ``found`` is already linked to, if it's taken.
    linked_team: str | None = None
    # Why the search couldn't be done: missing keys, or the service's error.
    error: str | None = None


class TeamLookup(BaseModel):
    name: str
    # True if a workbench team already has this name.
    name_taken: bool
    services: list[ServiceLookup]


ConnectOutcome = Literal["linked", "already_linked", "not_found", "taken", "not_set_up", "error"]


class ConnectResult(BaseModel):
    service_id: str
    outcome: ConnectOutcome
    message: str


class TeamConnected(BaseModel):
    """What "Find links" did for each service."""

    team: TeamRead
    results: list[ConnectResult]


class TeamServiceCreated(BaseModel):
    team: TeamRead
    # E.g. "Created the GitHub repository my-org/team-alpha."
    message: str
