"""HTTP endpoints under /api/auth."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.auth import service
from app.auth.dependencies import CurrentUser
from app.auth.schemas import ChangePasswordRequest, LoginRequest
from app.core.config import get_settings
from app.core.db import DbSession
from app.core.security import verify_password
from app.users.schemas import UserRead
from app.users.service import set_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserRead)
def login(body: LoginRequest, response: Response, db: DbSession) -> UserRead:
    """Check email + password and, if valid, set an HTTP-only session cookie."""
    user = service.authenticate(db, body.email, body.password)
    if user is None:
        # Same message whether the email or the password was wrong, on purpose.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token, expires_at = service.start_session(db, user)
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
    return UserRead.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession) -> None:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        service.end_session(db, token)
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    """Return the logged-in user. The web app calls this to check if you are logged in."""
    return UserRead.model_validate(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest, request: Request, user: CurrentUser, db: DbSession
) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    set_password(db, user, body.new_password)
    # Log out other browsers, but keep this one logged in.
    service.end_all_sessions(
        db, user, except_token=request.cookies.get(get_settings().session_cookie_name)
    )
