"""HTTP endpoints under /api/users. Superusers only."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.auth.dependencies import CurrentSuperuser, require_superuser
from app.auth.service import end_all_sessions
from app.core.db import DbSession
from app.users import service
from app.users.models import User
from app.users.schemas import UserCreate, UserRead, UserUpdate

router = APIRouter(
    prefix="/users",
    tags=["users"],
    # Every route in this router requires a superuser.
    dependencies=[Depends(require_superuser)],
)


@router.get("", response_model=list[UserRead])
def list_users(db: DbSession) -> list[User]:
    return list(db.scalars(select(User).order_by(User.email)))


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: DbSession) -> User:
    if service.get_user_by_email(db, body.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="A user with that email exists")
    return service.create_user(
        db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        is_superuser=body.is_superuser,
    )


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, body: UserUpdate, admin: CurrentSuperuser, db: DbSession) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

    # Guard rail: don't let an admin lock themselves out by accident.
    if user.id == admin.id and (body.is_active is False or body.is_superuser is False):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate or demote your own account",
        )

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.is_superuser is not None:
        user.is_superuser = body.is_superuser
    if body.is_active is not None:
        user.is_active = body.is_active
        if not body.is_active:
            end_all_sessions(db, user)
    if body.password is not None:
        service.set_password(db, user, body.password)
        end_all_sessions(db, user)

    db.commit()
    db.refresh(user)
    return user
