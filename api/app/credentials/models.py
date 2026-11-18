"""The ``credentials`` table: encrypted API keys and tokens.

``user_id`` decides the scope: a row with a ``user_id`` belongs to that user;
a row with ``user_id = NULL`` is system-wide. A unique index guarantees at most
one value per (user, key), and at most one system-wide value per key.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Credential(Base):
    __tablename__ = "credentials"
    __table_args__ = (
        Index(
            "uq_credentials_user_id_key",
            "user_id",
            "key",
            unique=True,
            # Treat NULLs as equal, so there can be only one system-wide row per key.
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(100))
    # Fernet-encrypted value (see app/core/crypto.py). Never the plain value.
    encrypted_value: Mapped[str] = mapped_column(Text)
    # Last 4 characters, so people can tell which key is saved without seeing it.
    hint: Mapped[str] = mapped_column(String(8))
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
