import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_session

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
        revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        if revision != "0002_document_versions":
            raise HTTPException(status_code=503, detail="Database migration required")
    except SQLAlchemyError:
        logger.warning("Database readiness check failed")
        raise HTTPException(
            status_code=503, detail="Database unavailable or not migrated"
        ) from None
    return {"status": "ready"}
