"""Make sure the superuser from the environment exists.

Runs every time the API container starts (see api/scripts/start.sh), so it
must be safe to run repeatedly:

* If no user has ``SUPERUSER_EMAIL``, one is created with ``SUPERUSER_PASSWORD``.
* If that user already exists, it is (re)marked active and superuser, but its
  password is NOT changed. This way, a password changed in the app is not
  overwritten on the next restart. To force a reset, use the CLI:
  ``python -m app.cli reset-password <email>``.
"""

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.users.service import create_user, get_user_by_email

logger = logging.getLogger(__name__)


def ensure_superuser(db: Session) -> None:
    settings = get_settings()
    email = settings.superuser_email
    user = get_user_by_email(db, email)

    if user is None:
        create_user(
            db,
            email=email,
            password=settings.superuser_password.get_secret_value(),
            full_name="Administrator",
            is_superuser=True,
        )
        logger.info("Created superuser %s", email)
        return

    if not (user.is_superuser and user.is_active):
        user.is_superuser = True
        user.is_active = True
        db.commit()
        logger.info("Restored superuser flags on %s", email)
    else:
        logger.info("Superuser %s already exists", email)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    with SessionLocal() as db:
        ensure_superuser(db)


if __name__ == "__main__":
    main()
