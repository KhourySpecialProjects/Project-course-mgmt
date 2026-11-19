"""Setting and clearing the session cookie. Shared by login and invite acceptance."""

from datetime import datetime

from fastapi import Response

from app.core.config import get_settings


def set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        expires=expires_at,
        httponly=True,  # JavaScript in the browser cannot read it
        secure=settings.session_cookie_secure,
        samesite="lax",  # not sent on cross-site POSTs (basic CSRF protection)
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(get_settings().session_cookie_name, path="/")
