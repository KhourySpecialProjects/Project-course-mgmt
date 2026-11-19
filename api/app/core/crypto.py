"""Encrypt and decrypt secrets (API keys, tokens) before they go in the database.

Unlike passwords, API keys must be *readable* later, because the app has to
send them to GitHub, Linear, Anthropic, etc. So they are encrypted (reversible
with the key) rather than hashed (one-way).

We use Fernet from the ``cryptography`` package: AES encryption plus a check
that detects tampering. The encryption key is derived from the
``APP_SECRET_KEY`` setting, so anyone with the database but without that
setting cannot read the stored API keys.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class DecryptionError(Exception):
    """A stored value could not be decrypted (usually: APP_SECRET_KEY changed)."""


@lru_cache
def _fernet() -> Fernet:
    secret = get_settings().app_secret_key.get_secret_value().encode()
    # Fernet needs exactly 32 bytes, base64-encoded. Hashing the setting lets
    # APP_SECRET_KEY be any string of any length.
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError("Stored value could not be decrypted") from exc
