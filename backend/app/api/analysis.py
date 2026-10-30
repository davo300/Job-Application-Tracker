from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict

from app.analysis.extraction import Extraction
from app.api.dependencies import CurrentUser, Database
from app.schemas.tracking import Page
from app.services.analysis import AnalysisService

router = APIRouter(tags=["analysis"])


class AnalysisOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    description_version_id: UUID
    provider: str
    provider_version: str
    schema_version: int
    structured_data: Extraction
    created_at: datetime


def service(db: Database, auth: CurrentUser):
    return AnalysisService(db, auth.user.id)


Service = Annotated[AnalysisService, Depends(service)]


@router.get("/descriptions/{identifier}/analyses", response_model=Page[AnalysisOutput])
def analyses(
    identifier: UUID,
    service: Service,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    rows, total = service.list(identifier, page, page_size)
    return {"items": [row[0] for row in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/descriptions/{identifier}/analyses", response_model=AnalysisOutput, status_code=201)
def analyze(identifier: UUID, service: Service, response: Response):
    row, created = service.create(identifier)
    if not created:
        response.status_code = 200
    return row
