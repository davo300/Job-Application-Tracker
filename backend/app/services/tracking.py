from datetime import UTC, datetime, time

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.entities import (
    Application,
    ApplicationEvent,
    Company,
    DescriptionVersion,
    Document,
    Job,
)
from app.repositories.tracking import TrackingRepository
from app.schemas.tracking import ApplicationOutput, CompanyInput, JobInput, JobOutput


class TrackingError(Exception):
    def __init__(self, status, detail):
        self.status, self.detail = status, detail


def required(value):
    if value is None:
        raise TrackingError(404, "Resource not found")
    return value


def db_values(data):
    values = data.model_dump(exclude_unset=True)
    for key in ("url", "website"):
        if values.get(key) is not None:
            values[key] = str(values[key])
    return values


class TrackingService:
    def __init__(self, db, user_id):
        self.db, self.user_id = db, user_id
        self.repo = TrackingRepository(db, user_id)

    def commit(self):
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise TrackingError(
                409, "Change conflicts with an existing reference or record"
            ) from None

    def company(self, identifier):
        return required(self.repo.company(identifier))

    def create_company(self, data):
        company = Company(user_id=self.user_id, **db_values(data))
        self.db.add(company)
        self.commit()
        return company

    def update_company(self, identifier, data):
        company = self.company(identifier)
        values = {key: getattr(company, key) for key in CompanyInput.model_fields}
        values.update(db_values(data))
        try:
            validated = CompanyInput.model_validate(values)
        except ValidationError:
            raise TrackingError(422, "Company name is required") from None
        for key, value in db_values(validated).items():
            setattr(company, key, value)
        self.commit()
        return company

    def delete_company(self, identifier):
        self.db.delete(self.company(identifier))
        self.commit()

    def job_output(self, job, company=None):
        company = company or self.company(job.company_id)
        return JobOutput(
            **{key: getattr(job, key) for key in JobInput.model_fields},
            id=job.id,
            company=company,
            archived_at=job.archived_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    def job(self, identifier):
        return self.job_output(required(self.repo.job(identifier)))

    def create_job(self, data):
        self.company(data.company_id)
        values = db_values(data)
        raw = values.pop("raw_description", None)
        job = Job(user_id=self.user_id, **values)
        self.db.add(job)
        self.db.flush()
        if raw:
            self.db.add(
                DescriptionVersion(user_id=self.user_id, job_id=job.id, version=1, raw_text=raw)
            )
        self.commit()
        return self.job_output(job)

    def update_job(self, identifier, data):
        job = required(self.repo.job(identifier, lock=True))
        values = db_values(data)
        raw_present = "raw_description" in values
        raw = values.pop("raw_description", None)
        if raw_present and (raw is None or not raw.strip()):
            raise TrackingError(422, "Description cannot be cleared; add a replacement version")
        archived = values.pop("archived", None)
        merged = {key: getattr(job, key) for key in JobInput.model_fields}
        merged.update(values)
        try:
            validated = JobInput.model_validate(merged)
        except ValidationError:
            raise TrackingError(
                422, "Check required job fields and salary range/currency/period"
            ) from None
        self.company(validated.company_id)
        for key, value in db_values(validated).items():
            setattr(job, key, value)
        if archived is not None:
            job.archived_at = (job.archived_at or datetime.now(UTC)) if archived else None
        if raw_present:
            self._append_description(job, raw)
        self.commit()
        return self.job_output(job)

    def _append_description(self, job, raw):
        latest = self.db.scalar(
            select(DescriptionVersion)
            .where(DescriptionVersion.job_id == job.id)
            .order_by(DescriptionVersion.version.desc())
            .limit(1)
        )
        if latest and latest.raw_text == raw:
            return latest, False
        description = DescriptionVersion(
            user_id=self.user_id,
            job_id=job.id,
            version=(latest.version + 1 if latest else 1),
            raw_text=raw,
        )
        self.db.add(description)
        job.updated_at = datetime.now(UTC)
        return description, True

    def append_description(self, identifier, data):
        job = required(self.repo.job(identifier, lock=True))
        description, created = self._append_description(job, data.raw_text)
        self.commit()
        return description, created

    def descriptions(self, identifier):
        required(self.repo.job(identifier))
        return self.repo.descriptions(identifier)

    def application_output(self, application, job=None, company=None):
        job = job or required(self.repo.job(application.job_id))
        return ApplicationOutput(
            resume_id=application.resume_id,
            cover_letter_id=application.cover_letter_id,
            id=application.id,
            job=self.job_output(job, company),
            applied_on=application.applied_on,
            attempt_number=application.attempt_number,
            current_stage=application.current_stage,
            status=application.status,
            notes=application.notes,
            created_at=application.created_at,
            updated_at=application.updated_at,
        )

    def application(self, identifier):
        return self.application_output(required(self.repo.application(identifier)))

    def create_application(self, data):
        # Lock the job so concurrent attempts allocate distinct attempt numbers.
        job = required(self.repo.job(data.job_id, lock=True))
        if job.archived_at:
            raise TrackingError(409, "Restore this job before recording an application")
        attempt = (
            self.db.scalar(
                select(func.max(Application.attempt_number)).where(
                    Application.job_id == job.id, Application.user_id == self.user_id
                )
            )
            or 0
        )
        self.validate_documents(data.resume_id, data.cover_letter_id)
        application = Application(
            resume_id=data.resume_id,
            cover_letter_id=data.cover_letter_id,
            user_id=self.user_id,
            job_id=job.id,
            applied_on=data.applied_on,
            notes=data.notes,
            attempt_number=attempt + 1,
        )
        self.db.add(application)
        self.db.flush()
        self.db.add(
            ApplicationEvent(
                application_id=application.id,
                event_type="applied",
                occurred_at=datetime.combine(data.applied_on, time.min, tzinfo=UTC),
            )
        )
        self.commit()
        return self.application_output(application, job)

    def update_application(self, identifier, data):
        application = required(self.repo.application(identifier, lock=True))
        values = db_values(data)
        self.validate_documents(values.get("resume_id"), values.get("cover_letter_id"), application)
        for key, value in values.items():
            setattr(application, key, value)
        self.commit()
        return self.application_output(application)

    def validate_documents(self, resume_id, cover_letter_id, application=None):
        # Lock referenced documents in stable order to avoid lock-order inversion.
        references = sorted(
            [
                (identifier, kind)
                for identifier, kind in [(resume_id, "resume"), (cover_letter_id, "cover_letter")]
                if identifier
            ],
            key=lambda item: str(item[0]),
        )
        for identifier, kind in references:
            document = required(self.repo.document(identifier, lock=True))
            if document.kind != kind:
                raise TrackingError(
                    422, f"Select a {kind.replace('_', ' ')} document for this field"
                )
            already_attached = (
                application is not None and getattr(application, f"{kind}_id") == identifier
            )
            if document.archived_at and not already_attached:
                raise TrackingError(409, "Restore an archived document before attaching it")

    def document(self, identifier):
        return required(self.repo.document(identifier))

    def create_document(self, data):
        document = Document(user_id=self.user_id, **db_values(data))
        self.db.add(document)
        self.commit()
        return document

    def archive_document(self, identifier, archived):
        document = required(self.repo.document(identifier, lock=True))
        document.archived_at = (document.archived_at or datetime.now(UTC)) if archived else None
        self.commit()
        return document

    def events(self, identifier, page, page_size):
        required(self.repo.application(identifier))
        return self.repo.events(identifier, page, page_size)

    def record_event(self, identifier, data):
        application = required(self.repo.application(identifier, lock=True))
        occurred = data.occurred_at.astimezone(UTC)
        now = datetime.now(UTC)
        initial = datetime.combine(application.applied_on, time.min, tzinfo=UTC)
        if occurred < initial or occurred > now:
            raise TrackingError(
                422,
                "Event time must be between application date and now; future appointments are not recorded events",
            )
        if data.event_type != "note":
            if application.status != "active":
                raise TrackingError(409, "This application is closed; you can still add notes")
            latest = self.db.scalar(
                select(func.max(ApplicationEvent.occurred_at)).where(
                    ApplicationEvent.application_id == application.id,
                    ApplicationEvent.event_type != "note",
                )
            )
            if latest is not None and occurred <= latest:
                raise TrackingError(
                    409, "Stage and outcome times must be later than the latest recorded transition"
                )
            if data.event_type in {"offer", "rejected", "withdrawn"}:
                application.status = data.event_type
            else:
                application.current_stage = data.event_type
        self.db.add(
            ApplicationEvent(
                application_id=application.id,
                event_type=data.event_type,
                occurred_at=occurred,
                notes=data.notes,
            )
        )
        application.updated_at = now
        self.commit()
        return self.application_output(application)
