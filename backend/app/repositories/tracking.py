from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import (
    Application,
    ApplicationEvent,
    Company,
    DescriptionVersion,
    Document,
    Job,
)


class TrackingRepository:
    def __init__(self, db: Session, user_id: UUID):
        self.db, self.user_id = db, user_id

    def company(self, identifier):
        return self.db.scalar(
            select(Company).where(Company.id == identifier, Company.user_id == self.user_id)
        )

    def job(self, identifier, lock=False):
        stmt = select(Job).where(Job.id == identifier, Job.user_id == self.user_id)
        return self.db.scalar(stmt.with_for_update() if lock else stmt)

    def application(self, identifier, lock=False):
        stmt = select(Application).where(
            Application.id == identifier, Application.user_id == self.user_id
        )
        return self.db.scalar(stmt.with_for_update() if lock else stmt)

    def descriptions(self, job_id):
        return list(
            self.db.scalars(
                select(DescriptionVersion)
                .where(
                    DescriptionVersion.job_id == job_id, DescriptionVersion.user_id == self.user_id
                )
                .order_by(DescriptionVersion.version.desc())
            )
        )

    def paginate(self, stmt, page, page_size):
        total = self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
        rows = self.db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
        return rows, total

    def companies(self, q, page, page_size):
        stmt = select(Company).where(Company.user_id == self.user_id)
        if q:
            stmt = stmt.where(Company.name.icontains(q, autoescape=True))
        return self.paginate(stmt.order_by(func.lower(Company.name), Company.id), page, page_size)

    def jobs(self, q, company_id, archived, page, page_size):
        stmt = (
            select(Job, Company)
            .join(Company, Job.company_id == Company.id)
            .where(Job.user_id == self.user_id)
        )
        stmt = stmt.where(Job.archived_at.is_not(None) if archived else Job.archived_at.is_(None))
        if q:
            stmt = stmt.where(
                or_(
                    Job.title.icontains(q, autoescape=True),
                    Company.name.icontains(q, autoescape=True),
                )
            )
        if company_id:
            stmt = stmt.where(Job.company_id == company_id)
        return self.paginate(stmt.order_by(Job.created_at.desc(), Job.id), page, page_size)

    def applications(
        self, *, q, company_id, status, location, date_from, date_to, sort, page, page_size
    ):
        # Filter/count application IDs without carrying full joined records through
        # the scan. Composite foreign keys guarantee the related job/company exist.
        stmt = select(Application.id).where(Application.user_id == self.user_id)
        if q:
            matching_companies = select(Company.id).where(
                Company.user_id == self.user_id,
                Company.name.icontains(q, autoescape=True),
            )
            matching_jobs = select(Job.id).where(
                Job.user_id == self.user_id,
                or_(
                    Job.title.icontains(q, autoescape=True),
                    Job.company_id.in_(matching_companies),
                ),
            )
            stmt = stmt.where(
                or_(
                    Application.job_id.in_(matching_jobs),
                    Application.notes.icontains(q, autoescape=True),
                )
            )
        if company_id or location:
            matching_jobs = select(Job.id).where(Job.user_id == self.user_id)
            if company_id:
                matching_jobs = matching_jobs.where(Job.company_id == company_id)
            if location:
                matching_jobs = matching_jobs.where(
                    Job.location.icontains(location, autoescape=True)
                )
            stmt = stmt.where(Application.job_id.in_(matching_jobs))
        if status:
            stmt = stmt.where(Application.status == status)
        if date_from:
            stmt = stmt.where(Application.applied_on >= date_from)
        if date_to:
            stmt = stmt.where(Application.applied_on <= date_to)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        ordering = {
            "newest": Application.applied_on.desc(),
            "oldest": Application.applied_on.asc(),
            "company": func.lower(Company.name),
            "title": func.lower(Job.title),
        }[sort]
        if sort in {"company", "title"}:
            stmt = stmt.join(Job, Application.job_id == Job.id)
            if sort == "company":
                stmt = stmt.join(Company, Job.company_id == Company.id)
        page_ids = (
            stmt.order_by(ordering, Application.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .subquery()
        )
        # Hydrate only the requested page and retain the same deterministic order.
        rows = self.db.execute(
            select(Application, Job, Company)
            .join(page_ids, Application.id == page_ids.c.id)
            .join(Job, Application.job_id == Job.id)
            .join(Company, Job.company_id == Company.id)
            .where(Application.user_id == self.user_id)
            .order_by(ordering, Application.id)
        ).all()
        return rows, total

    def document(self, identifier, lock=False):
        stmt = select(Document).where(Document.id == identifier, Document.user_id == self.user_id)
        return self.db.scalar(stmt.with_for_update() if lock else stmt)

    def documents(self, archived, page, page_size):
        stmt = select(Document).where(Document.user_id == self.user_id)
        stmt = stmt.where(
            Document.archived_at.is_not(None) if archived else Document.archived_at.is_(None)
        )
        return self.paginate(
            stmt.order_by(Document.created_at.desc(), Document.id), page, page_size
        )

    def events(self, identifier, page, page_size):
        stmt = (
            select(ApplicationEvent)
            .join(Application, Application.id == ApplicationEvent.application_id)
            .where(
                ApplicationEvent.application_id == identifier, Application.user_id == self.user_id
            )
        )
        return self.paginate(
            stmt.order_by(
                ApplicationEvent.occurred_at, ApplicationEvent.recorded_at, ApplicationEvent.id
            ),
            page,
            page_size,
        )
