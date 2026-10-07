from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.dependencies import CurrentUser, Database
from app.schemas.tracking import (
    ApplicationInput,
    ApplicationOutput,
    ApplicationPatch,
    CompanyInput,
    CompanyOutput,
    CompanyPatch,
    DescriptionInput,
    DescriptionOutput,
    DocumentInput,
    DocumentOutput,
    DocumentPatch,
    EventInput,
    EventOutput,
    JobCreate,
    JobOutput,
    JobPatch,
    Page,
    Status,
)
from app.services.tracking import TrackingService

router = APIRouter(tags=["tracking"])


def tracking_service(db: Database, auth: CurrentUser):
    return TrackingService(db, auth.user.id)


Service = Annotated[TrackingService, Depends(tracking_service)]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str | None, Query(max_length=200)]


@router.get("/companies", response_model=Page[CompanyOutput])
def companies(service: Service, q: Search = None, page: PageNumber = 1, page_size: PageSize = 25):
    rows, total = service.repo.companies(q, page, page_size)
    return {"items": [row[0] for row in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/companies", response_model=CompanyOutput, status_code=201)
def create_company(data: CompanyInput, service: Service):
    return service.create_company(data)


@router.get("/companies/{identifier}", response_model=CompanyOutput)
def company(identifier: UUID, service: Service):
    return service.company(identifier)


@router.patch("/companies/{identifier}", response_model=CompanyOutput)
def update_company(identifier: UUID, data: CompanyPatch, service: Service):
    return service.update_company(identifier, data)


@router.delete("/companies/{identifier}", status_code=204)
def delete_company(identifier: UUID, service: Service):
    service.delete_company(identifier)


@router.get("/jobs", response_model=Page[JobOutput])
def jobs(
    service: Service,
    q: Search = None,
    company_id: UUID | None = None,
    archived: bool = False,
    page: PageNumber = 1,
    page_size: PageSize = 25,
):
    rows, total = service.repo.jobs(q, company_id, archived, page, page_size)
    return {
        "items": [service.job_output(job, company) for job, company in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/jobs", response_model=JobOutput, status_code=201)
def create_job(data: JobCreate, service: Service):
    return service.create_job(data)


@router.get("/jobs/{identifier}", response_model=JobOutput)
def job(identifier: UUID, service: Service):
    return service.job(identifier)


@router.patch("/jobs/{identifier}", response_model=JobOutput)
def update_job(identifier: UUID, data: JobPatch, service: Service):
    return service.update_job(identifier, data)


@router.delete("/jobs/{identifier}", response_model=JobOutput)
def archive_job(identifier: UUID, service: Service):
    return service.update_job(identifier, JobPatch(archived=True))


@router.get("/jobs/{identifier}/descriptions", response_model=list[DescriptionOutput])
def descriptions(identifier: UUID, service: Service):
    return service.descriptions(identifier)


@router.post("/jobs/{identifier}/descriptions", response_model=DescriptionOutput, status_code=201)
def append_description(
    identifier: UUID, data: DescriptionInput, response: Response, service: Service
):
    description, created = service.append_description(identifier, data)
    response.status_code = 201 if created else 200
    return description


@router.get("/applications", response_model=Page[ApplicationOutput])
def applications(
    service: Service,
    q: Search = None,
    company_id: UUID | None = None,
    status: Status | None = None,
    location: Search = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: Literal["newest", "oldest", "company", "title"] = "newest",
    page: PageNumber = 1,
    page_size: PageSize = 25,
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="Start date must not follow end date")
    rows, total = service.repo.applications(
        q=q,
        company_id=company_id,
        status=status,
        location=location,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [
            service.application_output(application, job, company)
            for application, job, company in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/applications", response_model=ApplicationOutput, status_code=201)
def create_application(data: ApplicationInput, service: Service):
    return service.create_application(data)


@router.get("/applications/{identifier}", response_model=ApplicationOutput)
def application(identifier: UUID, service: Service):
    return service.application(identifier)


@router.patch("/applications/{identifier}", response_model=ApplicationOutput)
def update_application(identifier: UUID, data: ApplicationPatch, service: Service):
    return service.update_application(identifier, data)


@router.get("/applications/{identifier}/events", response_model=Page[EventOutput])
def events(identifier: UUID, service: Service, page: PageNumber = 1, page_size: PageSize = 25):
    rows, total = service.events(identifier, page, page_size)
    return {"items": [row[0] for row in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/applications/{identifier}/events", response_model=ApplicationOutput, status_code=201)
def record_event(identifier: UUID, data: EventInput, service: Service):
    return service.record_event(identifier, data)


@router.get("/documents", response_model=Page[DocumentOutput])
def documents(
    service: Service, archived: bool = False, page: PageNumber = 1, page_size: PageSize = 25
):
    rows, total = service.repo.documents(archived, page, page_size)
    return {"items": [row[0] for row in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/documents", response_model=DocumentOutput, status_code=201)
def create_document(data: DocumentInput, service: Service):
    return service.create_document(data)


@router.get("/documents/{identifier}", response_model=DocumentOutput)
def document(identifier: UUID, service: Service):
    return service.document(identifier)


@router.patch("/documents/{identifier}", response_model=DocumentOutput)
def archive_document(identifier: UUID, data: DocumentPatch, service: Service):
    return service.archive_document(identifier, data.archived)
