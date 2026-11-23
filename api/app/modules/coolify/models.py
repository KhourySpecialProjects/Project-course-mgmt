"""The ``server_jobs`` table: patch checks, patching, and image scans run on team servers.

They take minutes, so they run in the background after the request returns; the
page polls the job until it's finished. The log and result stay for later.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ServerJob(Base):
    __tablename__ = "server_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    # The Coolify server it ran on.
    server_uuid: Mapped[str] = mapped_column(String(64))
    server_name: Mapped[str] = mapped_column(String(200), default="")
    # patch_check | patch_security | patch_all | image_scan
    kind: Mapped[str] = mapped_column(String(30))
    # running | succeeded | failed
    status: Mapped[str] = mapped_column(String(20), default="running")
    log: Mapped[str] = mapped_column(Text, default="")
    # JSON: what was found (updates, scan counts, ...).
    result: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    started_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
