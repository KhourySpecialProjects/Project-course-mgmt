"""Describing an API key or token the app knows how to store.

Each kind of credential is declared once, in code, with a ``CredentialSpec``.
Users and admins can only save values for declared credentials, and the UI is
generated from these declarations (label, description, where to get one).
"""

from dataclasses import dataclass
from enum import StrEnum


class CredentialScope(StrEnum):
    # Each user saves their own value (e.g. a personal GitHub token, so actions
    # in GitHub are performed as that person). Managed on the Account page, or
    # in System settings for superusers.
    USER = "user"
    # One value for the whole app (e.g. the Anthropic API key the app uses).
    # Managed by superusers in the admin portal.
    SYSTEM = "system"
    # One value per student team (e.g. a Coolify API token made inside that team's
    # Coolify team, since Coolify tokens only see their own team). Managed from the
    # team's page; see app/teams/credentials.py.
    TEAM = "team"


@dataclass(frozen=True)
class CredentialSpec:
    # Stable identifier stored in the database. Never change it once in use.
    key: str
    label: str
    description: str
    scope: CredentialScope
    # Optional link to the page where the user can create the key.
    help_url: str | None = None
    # Example of the format, shown greyed out in the input box.
    placeholder: str = ""
    # False for keys that unlock an extra (e.g. automatic setup) but aren't needed to
    # use the module; a missing optional key doesn't make it "not configured".
    required: bool = True
