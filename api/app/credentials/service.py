"""Saving and reading encrypted credentials.

Use these from feature code to get a key when you need to call an external API:

    from app.credentials.service import get_system_credential, get_user_credential

    token = get_user_credential(db, user, "github_token")        # per-user
    api_key = get_system_credential(db, "anthropic_api_key")      # system-wide

Both return ``None`` if nothing is saved (or the saved value can no longer be
decrypted), so check for that and tell the user what to set up.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import DecryptionError, decrypt, encrypt
from app.credentials.models import Credential
from app.users.models import User

logger = logging.getLogger(__name__)


def _find(db: Session, user_id: int | None, key: str) -> Credential | None:
    owner = Credential.user_id.is_(None) if user_id is None else Credential.user_id == user_id
    return db.scalar(select(Credential).where(owner, Credential.key == key))


def list_saved(db: Session, user_id: int | None) -> dict[str, Credential]:
    """All saved credentials for a user (or system-wide when ``user_id`` is None), by key."""
    owner = Credential.user_id.is_(None) if user_id is None else Credential.user_id == user_id
    return {c.key: c for c in db.scalars(select(Credential).where(owner))}


def save(db: Session, *, user_id: int | None, key: str, value: str, updated_by: User) -> Credential:
    """Create or replace a credential."""
    cred = _find(db, user_id, key)
    if cred is None:
        cred = Credential(user_id=user_id, key=key)
        db.add(cred)
    cred.encrypted_value = encrypt(value)
    cred.hint = value[-4:] if len(value) >= 12 else ""  # don't reveal much of a short value
    cred.updated_by_id = updated_by.id
    db.commit()
    db.refresh(cred)
    return cred


def delete(db: Session, *, user_id: int | None, key: str) -> bool:
    cred = _find(db, user_id, key)
    if cred is None:
        return False
    db.delete(cred)
    db.commit()
    return True


def is_readable(cred: Credential) -> bool:
    """False if the value can't be decrypted (e.g. APP_SECRET_KEY was changed)."""
    try:
        decrypt(cred.encrypted_value)
    except DecryptionError:
        return False
    return True


def _read(cred: Credential | None) -> str | None:
    if cred is None:
        return None
    try:
        return decrypt(cred.encrypted_value)
    except DecryptionError:
        logger.warning("Credential %r (id=%s) could not be decrypted", cred.key, cred.id)
        return None


def get_user_credential(db: Session, user: User, key: str) -> str | None:
    return _read(_find(db, user.id, key))


def get_system_credential(db: Session, key: str) -> str | None:
    return _read(_find(db, None, key))
