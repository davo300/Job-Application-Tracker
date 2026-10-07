import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.security import token_digest
from app.services.auth import Authenticated, AuthService, InvalidCredentials

Database = Annotated[Session, Depends(get_session)]
Configuration = Annotated[Settings, Depends(get_settings)]


def auth_service(db: Database, settings: Configuration) -> AuthService:
    return AuthService(db, settings.session_ttl_hours)


Service = Annotated[AuthService, Depends(auth_service)]


def require_user(request: Request, service: Service, settings: Configuration) -> Authenticated:
    try:
        auth = service.authenticate(request.cookies.get(settings.session_cookie_name))
    except InvalidCredentials:
        raise HTTPException(status_code=401, detail="Authentication required") from None
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        token = request.headers.get("X-CSRF-Token", "")
        if (
            not token
            or len(token) > 128
            or not secrets.compare_digest(
                token_digest(token),
                auth.session.csrf_token_hash,
            )
        ):
            raise HTTPException(status_code=403, detail="Invalid CSRF token")
    return auth


CurrentUser = Annotated[Authenticated, Depends(require_user)]
