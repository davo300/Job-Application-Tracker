from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.analysis.extraction import Extraction
from app.matching.scoring import ProfileData, score
from app.models.entities import JobAnalysis, MatchResult, Profile, User

SCORER_VERSION = "1.0.0"


def analysis(db, user_id, identifier):
    row = db.scalar(
        select(JobAnalysis).where(JobAnalysis.id == identifier, JobAnalysis.user_id == user_id)
    )
    if row is None:
        raise HTTPException(404, "Analysis not found")
    return row


def save_profile_data(data, db, user_id):
    # Parent lock serializes initial creation as well as subsequent revision checks.
    db.scalar(select(User).where(User.id == user_id).with_for_update())
    row = db.scalar(select(Profile).where(Profile.user_id == user_id).with_for_update())
    if data.revision != (row.revision if row else 0):
        raise HTTPException(409, "Profile changed. Reload before saving.")
    if row:
        if row.data != data.data.model_dump():
            row.data = data.data.model_dump()
            row.revision += 1
    else:
        row = Profile(user_id=user_id, revision=1, data=data.data.model_dump())
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_match_result(identifier, db, user_id):
    source = analysis(db, user_id, identifier)
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id).with_for_update())
    if profile is None:
        raise HTTPException(409, "Create a profile before matching")
    data = ProfileData.model_validate(profile.data)
    extraction = Extraction.model_validate(source.structured_data)
    row = MatchResult(
        user_id=user_id,
        analysis_id=source.id,
        profile_id=profile.id,
        profile_revision=profile.revision,
        scorer_version=SCORER_VERSION,
        input_snapshot={
            "profile": data.model_dump(),
            "analysis": extraction.model_dump(),
            "provider": source.provider,
            "provider_version": source.provider_version,
            "schema_version": source.schema_version,
        },
        breakdown=score(data, extraction),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Match could not be saved") from None
    db.refresh(row)
    return row
