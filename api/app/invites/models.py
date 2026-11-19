"""The ``invites`` table: one row per invite link an admin has created."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.users.models import User


class InviteStatus(StrEnum):
    PENDING = "pending"  # can still be used
    ACCEPTED = "accepted"  # used to create an account
    REVOKED = "revoked"  # cancelled by an admin (or replaced by a newer invite)
    EXPIRED = "expired"  # not used in time


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    # SHA-256 of the token in the link. The link itself is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")

    @property
    def status(self) -> InviteStatus:
        if self.accepted_at is not None:
            return InviteStatus.ACCEPTED
        if self.revoked_at is not None:
            return InviteStatus.REVOKED
        if self.expires_at <= datetime.now(UTC):
            return InviteStatus.EXPIRED
        return InviteStatus.PENDING
