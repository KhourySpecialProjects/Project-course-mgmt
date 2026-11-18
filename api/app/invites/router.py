"""HTTP endpoints under /api/invites.

Admin endpoints (superusers only):
    GET    /api/invites               list invites
    POST   /api/invites               create an invite; response includes the one-time token
    POST   /api/invites/{id}/revoke   cancel a pending invite

Public endpoints (used by the person who received the link):
    GET    /api/invites/accept/{token}   check the link and show who it's for
    POST   /api/invites/accept/{token}   set a password, create the account, and log in
"""

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.cookies import set_session_cookie
from app.auth.dependencies import CurrentSuperuser, require_superuser
from app.auth.service import start_session
from app.core.db import DbSession
from app.invites import service
from app.invites.models import Invite
from app.invites.schemas import (
    InviteAccept,
    InviteCreate,
    InviteCreated,
    InvitePreview,
    InviteRead,
)
from app.invites.service import InviteError
from app.users.schemas import UserRead
from app.users.service import get_user_by_email

admin_router = APIRouter(
    prefix="/invites", tags=["invites"], dependencies=[Depends(require_superuser)]
)
public_router = APIRouter(prefix="/invites/accept", tags=["invites"])


def _to_read(invite: Invite) -> InviteRead:
    data = InviteRead.model_validate(invite)
    data.created_by_email = invite.created_by.email if invite.created_by else None
    return data


def _raise(err: InviteError) -> NoReturn:
    code = status.HTTP_410_GONE if err.gone else status.HTTP_404_NOT_FOUND
    raise HTTPException(code, detail=err.message)


# --- Admin ------------------------------------------------------------------


@admin_router.get("", response_model=list[InviteRead])
def list_invites(db: DbSession) -> list[InviteRead]:
    return [_to_read(i) for i in service.list_invites(db)]


@admin_router.post("", response_model=InviteCreated, status_code=status.HTTP_201_CREATED)
def create_invite(body: InviteCreate, admin: CurrentSuperuser, db: DbSession) -> InviteCreated:
    if get_user_by_email(db, body.email) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="A user with that email already exists"
        )
    invite, token = service.create_invite(
        db,
        email=body.email,
        full_name=body.full_name,
        is_superuser=body.is_superuser,
        created_by=admin,
    )
    return InviteCreated(**_to_read(invite).model_dump(), token=token)


@admin_router.post("/{invite_id}/revoke", response_model=InviteRead)
def revoke_invite(invite_id: int, db: DbSession) -> InviteRead:
    invite = db.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invite not found")
    service.revoke_invite(db, invite)
    db.refresh(invite)
    return _to_read(invite)


# --- Public -----------------------------------------------------------------


@public_router.get("/{token}", response_model=InvitePreview)
def preview_invite(token: str, db: DbSession) -> InvitePreview:
    try:
        invite = service.get_usable_invite(db, token)
    except InviteError as err:
        _raise(err)
    return InvitePreview(
        email=invite.email, full_name=invite.full_name, expires_at=invite.expires_at
    )


@public_router.post("/{token}", response_model=UserRead)
def accept_invite(token: str, body: InviteAccept, response: Response, db: DbSession) -> UserRead:
    try:
        user = service.accept_invite(db, token, full_name=body.full_name, password=body.password)
    except InviteError as err:
        db.rollback()
        _raise(err)

    session_token, expires_at = start_session(db, user)
    set_session_cookie(response, session_token, expires_at)
    return UserRead.model_validate(user)
