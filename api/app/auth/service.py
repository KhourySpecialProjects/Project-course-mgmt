"""Login, logout, and session lookup."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.models import AuthSession
from app.core.config import get_settings
from app.core.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    verify_password,
)
from app.users.models import User
from app.users.service import get_user_by_email

# Used to keep login timing similar whether or not the email exists, so an
# attacker cannot discover which emails have accounts by measuring response time.
_DUMMY_HASH = hash_password("timing-equalizer")


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Return the user if the email/password pair is valid and the account is active."""
    user = get_user_by_email(db, email)
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash) or not user.is_active:
        return None
    return user


def start_session(db: Session, user: User) -> tuple[str, datetime]:
    """Create a session for ``user``. Returns the raw token (for the cookie) and its expiry."""
    token = new_session_token()
    expires_at = datetime.now(UTC) + timedelta(hours=get_settings().session_ttl_hours)
    db.add(
        AuthSession(token_hash=hash_session_token(token), user_id=user.id, expires_at=expires_at)
    )
    db.commit()
    return token, expires_at


def get_user_for_token(db: Session, token: str) -> User | None:
    """Look up the user behind a session token, ignoring expired sessions."""
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_session_token(token),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    if session is None or not session.user.is_active:
        return None
    return session.user


def end_session(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_session_token(token)))
    db.commit()


def end_all_sessions(db: Session, user: User, *, except_token: str | None = None) -> None:
    """Log a user out everywhere (optionally keeping the current browser logged in)."""
    stmt = delete(AuthSession).where(AuthSession.user_id == user.id)
    if except_token is not None:
        stmt = stmt.where(AuthSession.token_hash != hash_session_token(except_token))
    db.execute(stmt)
    db.commit()
