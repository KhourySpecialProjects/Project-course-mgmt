"""The ``teams`` and ``team_links`` tables.

A team is a group of students working on one project. Each team has links to
its things in outside services: its GitHub repository, Linear team, Coolify
project, and any other links people add (a Figma file, a Slack channel, ...).

A link with a ``service_id`` belongs to a tool module that can create things
for teams (see ``TeamService`` in app/modules/base.py). A link without one is a
custom link that someone added by hand.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    links: Mapped[list["TeamLink"]] = relationship(
        back_populates="team",
        cascade="all, delete-orphan",
        order_by="TeamLink.id",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Team id={self.id} name={self.name!r}>"


# Team names are unique, ignoring upper/lower case ("Team A" and "team a" clash).
Index("uq_teams_lower_name", func.lower(Team.name), unique=True)


class TeamLink(Base):
    __tablename__ = "team_links"
    __table_args__ = (
        # At most one link per service per team. Custom links have no service_id,
        # and NULLs never clash in a unique index, so a team can have any number.
        UniqueConstraint("team_id", "service_id", name="uq_team_links_team_id_service_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    # Id of the tool module this link belongs to ("github", ...); NULL for a custom link.
    service_id: Mapped[str | None] = mapped_column(String(50))
    label: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(2000))
    # The thing's id in the outside service (GitHub repo id, Linear team id, Coolify
    # project uuid), when the workbench created or found it. Empty for pasted links.
    # Used to stop two teams from being linked to the same repo/team/project.
    external_id: Mapped[str] = mapped_column(String(200), default="")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    team: Mapped[Team] = relationship(back_populates="links")


class TeamCredential(Base):
    """An encrypted API key that belongs to one team (``CredentialScope.TEAM``).

    Same rules as the ``credentials`` table: values are Fernet-encrypted and never
    sent back; ``hint`` holds the last 4 characters.
    """

    __tablename__ = "team_credentials"
    __table_args__ = (UniqueConstraint("team_id", "key", name="uq_team_credentials_team_id_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(100))
    encrypted_value: Mapped[str] = mapped_column(Text)
    hint: Mapped[str] = mapped_column(String(8))
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
