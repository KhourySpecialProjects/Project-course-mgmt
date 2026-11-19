"""Small command-line helpers for admin tasks.

Run inside the API container, for example::

    docker compose exec api python -m app.cli create-user someone@example.com --superuser
    docker compose exec api python -m app.cli reset-password admin@example.com

You will be prompted for the password, so it never appears in your shell history.
"""

import argparse
import getpass
import sys

from app.auth.service import end_all_sessions
from app.core.db import SessionLocal
from app.core.security import MIN_PASSWORD_LENGTH
from app.users.service import create_user, get_user_by_email, set_password


def _prompt_password() -> str:
    password = getpass.getpass("New password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    return password


def cmd_create_user(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        if get_user_by_email(db, args.email):
            sys.exit(f"A user with email {args.email} already exists.")
        user = create_user(
            db,
            email=args.email,
            password=_prompt_password(),
            full_name=args.name,
            is_superuser=args.superuser,
        )
        print(f"Created {user.email} (superuser={user.is_superuser}).")


def cmd_reset_password(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        user = get_user_by_email(db, args.email)
        if user is None:
            sys.exit(f"No user with email {args.email}.")
        set_password(db, user, _prompt_password())
        end_all_sessions(db, user)
        print(f"Password updated for {user.email}. All their sessions were logged out.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("create-user", help="Create a new user")
    p.add_argument("email")
    p.add_argument("--name", default="", help="Full name")
    p.add_argument("--superuser", action="store_true", help="Make the user a superuser")
    p.set_defaults(func=cmd_create_user)

    p = sub.add_parser("reset-password", help="Set a new password for a user")
    p.add_argument("email")
    p.set_defaults(func=cmd_reset_password)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
