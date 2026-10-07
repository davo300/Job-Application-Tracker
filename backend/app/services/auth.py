from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import dummy_password_hash, hasher, new_token, token_digest, verify_password
from app.models.entities import Session as LoginSession
from app.models.entities import User
from app.repositories.auth import AuthRepository


class InvalidCredentials(Exception):
    pass


class AccountExists(Exception):
    pass


@dataclass(frozen=True)
class Authenticated:
    user: User
    session: LoginSession


@dataclass(frozen=True)
class IssuedSession:
    user: User
    token: str
    csrf_token: str


class AuthService:
    def __init__(self, db: Session, ttl_hours: int):
        self.db = db
        self.repo = AuthRepository(db)
        self.ttl_hours = ttl_hours

    def register(self, email: str, password: str, previous_token: str | None) -> IssuedSession:
        user = User(email=email, password_hash=hasher.hash(password))
        self.db.add(user)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            raise AccountExists from None
        return self._issue(user, previous_token)

    def login(self, email: str, password: str, previous_token: str | None) -> IssuedSession:
        user = self.repo.find_user(email)
        encoded = user.password_hash if user else dummy_password_hash()
        if not verify_password(encoded, password) or user is None:
            raise InvalidCredentials
        if hasher.check_needs_rehash(encoded):
            user.password_hash = hasher.hash(password)
        return self._issue(user, previous_token)

    def _issue(self, user: User, previous_token: str | None) -> IssuedSession:
        now = datetime.now(UTC)
        token, csrf = new_token(), new_token()
        if previous_token:
            self.repo.revoke(token_digest(previous_token))
        self.repo.remove_expired(now)
        self.db.add(
            LoginSession(
                user_id=user.id,
                token_hash=token_digest(token),
                csrf_token_hash=token_digest(csrf),
                expires_at=now + timedelta(hours=self.ttl_hours),
            )
        )
        self.db.commit()
        self.db.refresh(user)
        return IssuedSession(user=user, token=token, csrf_token=csrf)

    def authenticate(self, token: str | None) -> Authenticated:
        if not token or len(token) > 128:
            raise InvalidCredentials
        session = self.repo.find_session(token_digest(token), datetime.now(UTC))
        user = self.repo.user_by_id(session.user_id) if session else None
        if session is None or user is None:
            raise InvalidCredentials
        return Authenticated(user=user, session=session)

    def logout(self, token: str) -> None:
        self.repo.revoke(token_digest(token))
        self.db.commit()
