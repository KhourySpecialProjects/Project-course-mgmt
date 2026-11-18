"""Creating, revoking, and accepting invites."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token, new_token
from app.invites.models import Invite, InviteStatus
from app.users.models import User
from app.users.service import create_user, get_user_by_email, normalize_email


class InviteError(Exception):
    """An invite can't be used. ``message`` is safe to show to the user."""

    def __init__(self, message: str, *, gone: bool = False) -> None:
        super().__init__(message)
        self.message = message
        # True when the invite exists but is used up / expired / revoked.
        self.gone = gone


def list_invites(db: Session) -> list[Invite]:
    return list(db.scalars(select(Invite).order_by(Invite.created_at.desc(), Invite.id.desc())))


def create_invite(
    db: Session, *, email: str, full_name: str, is_superuser: bool, created_by: User
) -> tuple[Invite, str]:
    """Create an invite and return it with its raw token (shown to the admin only once).

    Any earlier pending invite for the same email is revoked, so there is only
    ever one working link per person. That's also how an admin "resends" a
    lost link: invite the same email again.
    """
    email = normalize_email(email)
    now = datetime.now(UTC)
    db.execute(
        update(Invite)
        .where(
            Invite.email == email,
            Invite.accepted_at.is_(None),
            Invite.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    token = new_token()
    invite = Invite(
        email=email,
        full_name=full_name.strip(),
        is_superuser=is_superuser,
        token_hash=hash_token(token),
        created_by_id=created_by.id,
        expires_at=now + timedelta(hours=get_settings().invite_ttl_hours),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite, token


def revoke_invite(db: Session, invite: Invite) -> None:
    if invite.status == InviteStatus.PENDING:
        invite.revoked_at = datetime.now(UTC)
        db.commit()


def get_usable_invite(db: Session, token: str, *, lock: bool = False) -> Invite:
    """Find the invite for ``token`` or raise ``InviteError`` explaining why it can't be used.

    ``lock=True`` locks the row until the transaction ends, so two people
    clicking "Create account" at the same moment can't both use one invite.
    """
    stmt = select(Invite).where(Invite.token_hash == hash_token(token))
    if lock:
        stmt = stmt.with_for_update(of=Invite)
    invite = db.scalar(stmt)

    if invite is None:
        raise InviteError("This invite link is not valid. Check that you copied all of it.")
    match invite.status:
        case InviteStatus.ACCEPTED:
            raise InviteError("This invite link has already been used.", gone=True)
        case InviteStatus.REVOKED:
            raise InviteError("This invite link has been cancelled.", gone=True)
        case InviteStatus.EXPIRED:
            raise InviteError("This invite link has expired.", gone=True)
    return invite


def accept_invite(db: Session, token: str, *, full_name: str, password: str) -> User:
    """Create the invited user's account and mark the invite as used."""
    invite = get_usable_invite(db, token, lock=True)
    if get_user_by_email(db, invite.email) is not None:
        raise InviteError("An account with this email already exists. Try signing in instead.")

    user = create_user(
        db,
        email=invite.email,
        password=password,
        full_name=full_name.strip() or invite.full_name,
        is_superuser=invite.is_superuser,
        commit=False,
    )
    invite.accepted_at = datetime.now(UTC)
    invite.accepted_user_id = user.id
    db.commit()  # user + invite saved together, or neither
    db.refresh(user)
    return user
