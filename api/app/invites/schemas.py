from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import MIN_PASSWORD_LENGTH
from app.invites.models import InviteStatus


class InviteCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(default="", max_length=200)
    is_superuser: bool = False


class InviteRead(BaseModel):
    """An invite as shown to admins. Never includes the token."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_superuser: bool
    status: InviteStatus
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    created_by_email: str | None = None


class InviteCreated(InviteRead):
    """Returned once, right after creating an invite. The only time the token is visible."""

    token: str


class InvitePreview(BaseModel):
    """What the person opening an invite link sees before accepting."""

    email: EmailStr
    full_name: str
    expires_at: datetime


class InviteAccept(BaseModel):
    full_name: str = Field(default="", max_length=200)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)
