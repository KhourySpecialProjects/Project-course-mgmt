"""HTTP endpoints under /api/credentials.

Values are write-only: you can set, replace, or remove a key, but the API never
sends a saved value back. Responses show only whether a value is set and its
last 4 characters.

    GET    /api/credentials/me               your personal keys        (any logged-in user)
    PUT    /api/credentials/me/{key}         save / replace one
    DELETE /api/credentials/me/{key}         remove one

    GET    /api/credentials/system           system-wide keys          (superusers only)
    PUT    /api/credentials/system/{key}
    DELETE /api/credentials/system/{key}
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentSuperuser, CurrentUser, require_superuser
from app.core.db import DbSession
from app.credentials import registry, service
from app.credentials.models import Credential
from app.credentials.schemas import CredentialStatus, CredentialUpdate
from app.credentials.spec import CredentialScope, CredentialSpec

router = APIRouter(prefix="/credentials", tags=["credentials"])


def _status(spec: CredentialSpec, cred: Credential | None) -> CredentialStatus:
    return CredentialStatus(
        key=spec.key,
        label=spec.label,
        description=spec.description,
        scope=spec.scope,
        help_url=spec.help_url,
        placeholder=spec.placeholder,
        is_set=cred is not None,
        hint=cred.hint if cred else "",
        readable=service.is_readable(cred) if cred else True,
        updated_at=cred.updated_at if cred else None,
    )


def _list(db: Session, scope: CredentialScope, user_id: int | None) -> list[CredentialStatus]:
    saved = service.list_saved(db, user_id)
    return [_status(spec, saved.get(spec.key)) for spec in registry.specs_for(scope)]


def _spec_or_404(key: str, scope: CredentialScope) -> CredentialSpec:
    spec = registry.get_spec(key, scope)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown {scope} credential: {key}")
    return spec


# --- Personal ---------------------------------------------------------------


@router.get("/me", response_model=list[CredentialStatus])
def list_mine(user: CurrentUser, db: DbSession) -> list[CredentialStatus]:
    return _list(db, CredentialScope.USER, user.id)


@router.put("/me/{key}", response_model=CredentialStatus)
def set_mine(
    key: str, body: CredentialUpdate, user: CurrentUser, db: DbSession
) -> CredentialStatus:
    spec = _spec_or_404(key, CredentialScope.USER)
    cred = service.save(db, user_id=user.id, key=key, value=body.value, updated_by=user)
    return _status(spec, cred)


@router.delete("/me/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mine(key: str, user: CurrentUser, db: DbSession) -> None:
    _spec_or_404(key, CredentialScope.USER)
    service.delete(db, user_id=user.id, key=key)


# --- System-wide (superusers) -----------------------------------------------


@router.get(
    "/system",
    response_model=list[CredentialStatus],
    dependencies=[Depends(require_superuser)],
)
def list_system(db: DbSession) -> list[CredentialStatus]:
    return _list(db, CredentialScope.SYSTEM, None)


@router.put("/system/{key}", response_model=CredentialStatus)
def set_system(
    key: str, body: CredentialUpdate, admin: CurrentSuperuser, db: DbSession
) -> CredentialStatus:
    spec = _spec_or_404(key, CredentialScope.SYSTEM)
    cred = service.save(db, user_id=None, key=key, value=body.value, updated_by=admin)
    return _status(spec, cred)


@router.delete(
    "/system/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_superuser)],
)
def delete_system(key: str, db: DbSession) -> None:
    _spec_or_404(key, CredentialScope.SYSTEM)
    service.delete(db, user_id=None, key=key)
