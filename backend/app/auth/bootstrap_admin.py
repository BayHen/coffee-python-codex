"""Interactive, one-time bootstrap of the first Admin account."""

import argparse
import getpass
import secrets
import sys
from collections.abc import Sequence

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.auth.security import hash_password
from app.db.models import Role, User
from app.db.session import get_session_factory

ROLE_NAMES = ("Admin", "Manager", "Staff")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the first Admin account")
    parser.add_argument("--email", required=True, help="Admin email address")
    args = parser.parse_args(argv)

    if not sys.stdin.isatty():
        print("Bootstrap requires an interactive terminal", file=sys.stderr)
        return 1
    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email)).lower()
    except ValidationError:
        print("Invalid email address", file=sys.stderr)
        return 1

    password = getpass.getpass("New Admin password (at least 12 characters): ")
    confirm = getpass.getpass("Confirm Admin password: ")
    if len(password) < 12 or len(password) > 1024 or not password.strip():
        print("Password must contain 12-1024 characters", file=sys.stderr)
        return 1
    if not secrets.compare_digest(password, confirm):
        print("Passwords do not match", file=sys.stderr)
        return 1

    try:
        with get_session_factory()() as db, db.begin():
            for name in ROLE_NAMES:
                db.execute(insert(Role).values(name=name).on_conflict_do_nothing())
            admin_role = db.scalar(
                select(Role).where(Role.name == "Admin").with_for_update()
            )
            if admin_role is None:
                raise RuntimeError("Admin role could not be created")
            if db.scalar(select(User.id).where(User.role_id == admin_role.id)):
                raise RuntimeError("An Admin account already exists")
            if db.scalar(select(User.id).where(User.email == email)):
                raise RuntimeError("Email is already registered")
            db.add(
                User(
                    role_id=admin_role.id,
                    email=email,
                    password_hash=hash_password(password),
                    is_active=True,
                )
            )
    except (RuntimeError, SQLAlchemyError) as exc:
        if isinstance(exc, SQLAlchemyError):
            print("Bootstrap failed: database operation failed", file=sys.stderr)
        else:
            print(f"Bootstrap failed: {exc}", file=sys.stderr)
        return 1

    print(f"Admin account created: {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
