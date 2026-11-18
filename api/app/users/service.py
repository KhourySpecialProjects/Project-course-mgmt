"""User business logic, kept separate from HTTP concerns so it can be reused
(by the router, the bootstrap step, the CLI, and tests)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.users.models import User


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str = "",
    is_superuser: bool = False,
) -> User:
    user = User(
        email=normalize_email(email),
        full_name=full_name,
        password_hash=hash_password(password),
        is_superuser=is_superuser,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_password(db: Session, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    db.commit()
