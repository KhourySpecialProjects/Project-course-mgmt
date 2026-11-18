"""Imports every database model so SQLAlchemy (and Alembic) know about all tables.

When you add a new ``models.py`` anywhere in the app, import it here too.
Alembic's autogenerate only sees tables whose models have been imported.
"""

from app.auth.models import AuthSession
from app.core.db import Base
from app.users.models import User

__all__ = ["AuthSession", "Base", "User"]
