"""Request and response shapes for user endpoints.

Pydantic models ("schemas") describe the JSON that goes in and out of the API.
FastAPI uses them to validate requests and to generate the interactive docs at
/api/docs. They are deliberately separate from the database model so that
fields like ``password_hash`` can never leak into a response.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import MIN_PASSWORD_LENGTH


class UserRead(BaseModel):
    """A user as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    is_superuser: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(default="", max_length=200)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)
    is_superuser: bool = False


class UserUpdate(BaseModel):
    """Fields an admin may change on another user. Omitted fields are left alone."""

    full_name: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None
    is_superuser: bool | None = None
    password: str | None = Field(default=None, min_length=MIN_PASSWORD_LENGTH, max_length=200)
