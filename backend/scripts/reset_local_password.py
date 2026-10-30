"""Interactive recovery for a development database; never accepts password arguments."""

import argparse
import getpass
import sys

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import build_engine
from app.core.security import hasher
from app.models.entities import Session as LoginSession
from app.models.entities import User


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    args = parser.parse_args()
    settings = get_settings()
    if settings.environment != "development":
        parser.error("This command is only available in development")
    if not sys.stdin.isatty():
        parser.error("Run interactively in Terminal so password input stays hidden")
    password = getpass.getpass("New password (12–128 characters): ")
    if not 12 <= len(password) <= 128:
        parser.error("Password must contain 12–128 characters")
    if password != getpass.getpass("Confirm new password: "):
        parser.error("Passwords do not match; nothing changed")
    engine = build_engine(settings.database_url)
    try:
        with Session(engine) as db, db.begin():
            user = db.scalar(
                select(User).where(User.email == args.email.strip().lower()).with_for_update()
            )
            if user is None:
                parser.error("Account not found; nothing changed")
            user.password_hash = hasher.hash(password)
            db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
        print("Password reset. Existing sessions revoked. Sign in with your new password.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
