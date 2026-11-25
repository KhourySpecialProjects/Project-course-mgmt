"""Saving and reading API keys that belong to one team (``CredentialScope.TEAM``).

    from app.teams.credentials import get_team_credential

    token = get_team_credential(db, team.id, "coolify_team_token")

Returns ``None`` if nothing is saved (or it can't be decrypted any more). Like all
keys, values are encrypted at rest and never returned by the API or logged.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import DecryptionError, decrypt, encrypt
from app.teams.models import TeamCredential
from app.users.models import User

logger = logging.getLogger(__name__)


def _find(db: Session, team_id: int, key: str) -> TeamCredential | None:
    return db.scalar(
        select(TeamCredential).where(TeamCredential.team_id == team_id, TeamCredential.key == key)
    )


def list_saved(db: Session, team_id: int) -> dict[str, TeamCredential]:
    rows = db.scalars(select(TeamCredential).where(TeamCredential.team_id == team_id))
    return {c.key: c for c in rows}


def save(db: Session, *, team_id: int, key: str, value: str, updated_by: User) -> TeamCredential:
    cred = _find(db, team_id, key)
    if cred is None:
        cred = TeamCredential(team_id=team_id, key=key)
        db.add(cred)
    cred.encrypted_value = encrypt(value)
    cred.hint = value[-4:] if len(value) >= 12 else ""
    cred.updated_by_id = updated_by.id
    db.commit()
    db.refresh(cred)
    return cred


def delete(db: Session, *, team_id: int, key: str) -> bool:
    cred = _find(db, team_id, key)
    if cred is None:
        return False
    db.delete(cred)
    db.commit()
    return True


def is_readable(cred: TeamCredential) -> bool:
    try:
        decrypt(cred.encrypted_value)
    except DecryptionError:
        return False
    return True


def get_team_credential(db: Session, team_id: int, key: str) -> str | None:
    cred = _find(db, team_id, key)
    if cred is None:
        return None
    try:
        return decrypt(cred.encrypted_value)
    except DecryptionError:
        logger.warning("Team credential %r (id=%s) could not be decrypted", key, cred.id)
        return None
