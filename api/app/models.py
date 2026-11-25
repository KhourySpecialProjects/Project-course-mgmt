"""Imports every database model so SQLAlchemy (and Alembic) know about all tables.

When you add a new ``models.py`` anywhere in the app, import it here too.
Alembic's autogenerate only sees tables whose models have been imported.
"""

from app.auth.models import AuthSession
from app.core.db import Base
from app.credentials.models import Credential
from app.invites.models import Invite
from app.modules.coolify.models import ServerJob
from app.teams.models import Team, TeamCredential, TeamLink, TeamMember
from app.users.models import User

__all__ = [
    "AuthSession",
    "Base",
    "Credential",
    "Invite",
    "ServerJob",
    "Team",
    "TeamCredential",
    "TeamLink",
    "TeamMember",
    "User",
]
