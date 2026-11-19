"""Password hashing and session-token helpers.

Passwords are never stored. We store an Argon2 *hash* of the password, which
can be checked against a login attempt but cannot be turned back into the
original password.

Random tokens (login sessions, invite links) work the same way: the user
holds the random token (in a cookie or a link), and the database stores only
a SHA-256 hash of it. Someone who reads the database cannot use the hashes.
"""

import hashlib
import secrets

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()  # Argon2id with sensible defaults

MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def new_token() -> str:
    """A long, random, URL-safe token (for session cookies and invite links)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 of a token, for storing in the database."""
    return hashlib.sha256(token.encode()).hexdigest()
