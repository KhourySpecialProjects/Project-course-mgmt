"""FastAPI dependencies for protecting routes.

Add one of these to a route handler's parameters and FastAPI will run it
before the handler:

    @router.get("/something")
    def something(user: CurrentUser) -> ...:        # any logged-in user
        ...

    @router.delete("/danger")
    def danger(admin: CurrentSuperuser) -> ...:     # superusers only
        ...

To protect *every* route in a router, pass the dependency to the router:

    router = APIRouter(dependencies=[Depends(require_user)])
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.auth.service import get_user_for_token
from app.core.config import get_settings
from app.core.db import DbSession
from app.users.models import User


def require_user(request: Request, db: DbSession) -> User:
    token = request.cookies.get(get_settings().session_cookie_name)
    user = get_user_for_token(db, token) if token else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    return user


def require_superuser(user: Annotated[User, Depends(require_user)]) -> User:
    if not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required")
    return user


CurrentUser = Annotated[User, Depends(require_user)]
CurrentSuperuser = Annotated[User, Depends(require_superuser)]
