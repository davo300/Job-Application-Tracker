from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.extraction import DeterministicProvider, Extraction, Provider, validate_evidence
from app.models.entities import DescriptionVersion, JobAnalysis
from app.services.tracking import TrackingError


class AnalysisService:
    def __init__(self, db: Session, user_id: UUID, provider: Provider | None = None):
        self.db, self.user_id = db, user_id
        self.provider = provider or DeterministicProvider()

    def description(self, identifier, lock=False):
        query = select(DescriptionVersion).where(
            DescriptionVersion.id == identifier, DescriptionVersion.user_id == self.user_id
        )
        row = self.db.scalar(query.with_for_update() if lock else query)
        if row is None:
            raise TrackingError(404, "Description not found")
        return row

    def list(self, identifier, page, page_size):
        self.description(identifier)
        from app.repositories.tracking import TrackingRepository

        return TrackingRepository(self.db, self.user_id).paginate(
            select(JobAnalysis)
            .where(
                JobAnalysis.description_version_id == identifier,
                JobAnalysis.user_id == self.user_id,
            )
            .order_by(JobAnalysis.created_at.desc(), JobAnalysis.id),
            page,
            page_size,
        )

    def create(self, identifier):
        description = self.description(identifier, lock=True)
        existing = self.db.scalar(
            select(JobAnalysis).where(
                JobAnalysis.description_version_id == identifier,
                JobAnalysis.user_id == self.user_id,
                JobAnalysis.provider == self.provider.name,
                JobAnalysis.provider_version == self.provider.version,
                JobAnalysis.schema_version == 1,
            )
        )
        if existing:
            return existing, False
        try:
            result = Extraction.model_validate(self.provider.extract(description.raw_text))
            validate_evidence(result, description.raw_text)
        except (ValueError, TypeError):
            self.db.rollback()
            raise TrackingError(502, "Analysis provider returned invalid evidence") from None
        row = JobAnalysis(
            user_id=self.user_id,
            description_version_id=identifier,
            provider=self.provider.name,
            provider_version=self.provider.version,
            schema_version=1,
            structured_data=result.model_dump(),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row, True
