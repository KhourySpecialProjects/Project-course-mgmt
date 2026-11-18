from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.credentials.spec import CredentialScope


class CredentialStatus(BaseModel):
    """A credential as shown in the UI. The secret value itself is NEVER included."""

    key: str
    label: str
    description: str
    scope: CredentialScope
    help_url: str | None
    placeholder: str
    is_set: bool
    # Last 4 characters of the saved value, e.g. "a1b2" (empty for short values).
    hint: str
    # False if a value is saved but can't be decrypted (re-enter it).
    readable: bool
    updated_at: datetime | None


class CredentialUpdate(BaseModel):
    value: str = Field(min_length=1, max_length=4096)

    @field_validator("value")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        # Pasted keys often carry a stray space or newline.
        v = v.strip()
        if not v:
            raise ValueError("Value cannot be blank")
        return v
