from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.dependencies import CurrentUser, Database
from app.matching.scoring import ProfileData
from app.models.entities import MatchResult, Profile
from app.schemas.tracking import Page
from app.services.matching import analysis, create_match_result, save_profile_data

router = APIRouter(tags=["matching"])
SCORER_VERSION = "1.0.0"


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int
    data: ProfileData


class ProfileOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    revision: int
    data: ProfileData


class MatchOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    analysis_id: UUID
    profile_revision: int
    scorer_version: str
    input_snapshot: dict
    breakdown: dict
    created_at: datetime


@router.get("/profile", response_model=ProfileOutput | None)
def profile(db: Database, auth: CurrentUser):
    return db.scalar(select(Profile).where(Profile.user_id == auth.user.id))


@router.put("/profile", response_model=ProfileOutput)
def save_profile(data: ProfileInput, db: Database, auth: CurrentUser):
    return save_profile_data(data, db, auth.user.id)


@router.post("/analyses/{identifier}/matches", response_model=MatchOutput, status_code=201)
def create_match(identifier: UUID, db: Database, auth: CurrentUser):
    return create_match_result(identifier, db, auth.user.id)


@router.get("/analyses/{identifier}/matches", response_model=Page[MatchOutput])
def matches(
    identifier: UUID,
    db: Database,
    auth: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    from app.repositories.tracking import TrackingRepository

    analysis(db, auth.user.id, identifier)
    rows, total = TrackingRepository(db, auth.user.id).paginate(
        select(MatchResult)
        .where(MatchResult.analysis_id == identifier, MatchResult.user_id == auth.user.id)
        .order_by(MatchResult.created_at.desc(), MatchResult.id),
        page,
        page_size,
    )
    return {"items": [r[0] for r in rows], "total": total, "page": page, "page_size": page_size}
