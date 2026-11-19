"""The contract every tool module implements.

A *tool module* is a self-contained integration (GitHub, Linear, ...). The core
app knows nothing about any particular tool; it just loops over the registered
modules (see ``app/modules/__init__.py``) and mounts each one's router at
``/api/tools/<id>``.
"""

from dataclasses import dataclass, field

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.credentials.service import get_system_credential, get_user_credential
from app.credentials.spec import CredentialScope, CredentialSpec
from app.users.models import User


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

    def missing_credentials(self, db: Session, user: User) -> list[CredentialSpec]:
        """The credentials still needed before ``user`` can use this module."""
        missing = []
        for spec in self.credentials:
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


class ToolStatus(BaseModel):
    """What each module's ``GET /api/tools/<id>/status`` returns."""

    configured: bool
    message: str
    # Keys of credentials still to be added, and where they're managed.
    missing_user_credentials: list[str] = []
    missing_system_credentials: list[str] = []


def _join_labels(specs: list[CredentialSpec]) -> str:
    """'A', 'A and B', or 'A, B, and C'."""
    labels = [s.label for s in specs]
    if len(labels) <= 2:
        return " and ".join(labels)
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def status_for(module: ToolModule, db: Session, user: User) -> ToolStatus:
    """A ready-made status response that any module can return from its /status endpoint."""
    missing = module.missing_credentials(db, user)
    if not missing:
        return ToolStatus(configured=True, message=f"{module.name} is ready to use.")

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
    )
