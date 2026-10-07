from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import Session as LoginSession
from app.models.entities import User


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_user(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def find_session(self, digest: str, now: datetime) -> LoginSession | None:
        return self.db.scalar(
            select(LoginSession).where(
                LoginSession.token_hash == digest,
                LoginSession.expires_at > now,
            )
        )

    def user_by_id(self, identifier: UUID) -> User | None:
        return self.db.get(User, identifier)

    def revoke(self, digest: str) -> None:
        self.db.execute(delete(LoginSession).where(LoginSession.token_hash == digest))

    def remove_expired(self, now: datetime) -> None:
        self.db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
