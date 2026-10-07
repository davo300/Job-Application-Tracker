from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

RawText = Annotated[str, StringConstraints(strip_whitespace=False, max_length=100000)]
T = TypeVar("T")
Stage = Literal[
    "applied",
    "assessment",
    "recruiter_screen",
    "technical_interview",
    "behavioral_interview",
    "final_interview",
]
Status = Literal["active", "offer", "rejected", "withdrawn"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CompanyInput(Input):
    name: str = Field(min_length=1, max_length=250)
    website: HttpUrl | None = None
    location: str | None = Field(default=None, max_length=250)
    notes: str | None = Field(default=None, max_length=20000)


class CompanyPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=250)
    website: HttpUrl | None = None
    location: str | None = Field(default=None, max_length=250)
    notes: str | None = Field(default=None, max_length=20000)


class CompanyOutput(CompanyInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime


class JobInput(Input):
    company_id: UUID
    title: str = Field(min_length=1, max_length=300)
    url: HttpUrl | None = None
    location: str | None = Field(default=None, max_length=250)
    work_arrangement: Literal["remote", "hybrid", "on_site"] | None = None
    employment_type: (
        Literal["full_time", "part_time", "internship", "contract", "temporary", "other"] | None
    ) = None
    salary_min: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    salary_max: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    salary_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    salary_period: Literal["hour", "month", "year"] | None = None
    posted_on: date | None = None
    deadline_on: date | None = None

    @model_validator(mode="after")
    def validate_salary(self):
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_max < self.salary_min
        ):
            raise ValueError("Salary maximum must be at least the minimum")
        if (self.salary_min is not None or self.salary_max is not None) and (
            not self.salary_currency or not self.salary_period
        ):
            raise ValueError("Salary requires currency and period")
        return self


class JobCreate(JobInput):
    raw_description: RawText | None = None

    @field_validator("raw_description")
    @classmethod
    def description_has_text(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Description must contain text when supplied")
        return value


class JobPatch(Input):
    company_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    url: HttpUrl | None = None
    location: str | None = Field(default=None, max_length=250)
    work_arrangement: Literal["remote", "hybrid", "on_site"] | None = None
    employment_type: (
        Literal["full_time", "part_time", "internship", "contract", "temporary", "other"] | None
    ) = None
    salary_min: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    salary_max: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    salary_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    salary_period: Literal["hour", "month", "year"] | None = None
    posted_on: date | None = None
    deadline_on: date | None = None
    raw_description: RawText | None = None
    archived: bool | None = None


class JobOutput(JobInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company: CompanyOutput
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DescriptionInput(Input):
    raw_text: RawText

    @field_validator("raw_text")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Description must contain text")
        return value


class DescriptionOutput(DescriptionInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    version: int
    created_at: datetime


class ApplicationInput(Input):
    resume_id: UUID | None = None
    cover_letter_id: UUID | None = None
    job_id: UUID
    applied_on: date
    notes: str | None = Field(default=None, max_length=20000)


class ApplicationPatch(Input):
    resume_id: UUID | None = None
    cover_letter_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=20000)


class ApplicationOutput(BaseModel):
    resume_id: UUID | None = None
    cover_letter_id: UUID | None = None
    id: UUID
    job: JobOutput
    applied_on: date
    attempt_number: int
    current_stage: Stage
    status: Status
    notes: str | None
    created_at: datetime
    updated_at: datetime


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


EventType = Literal[
    "assessment",
    "recruiter_screen",
    "technical_interview",
    "behavioral_interview",
    "final_interview",
    "offer",
    "rejected",
    "withdrawn",
    "note",
]


class EventInput(Input):
    event_type: EventType
    occurred_at: AwareDatetime
    notes: str | None = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def note_has_text(self):
        if self.event_type == "note" and not self.notes:
            raise ValueError("Note events require text")
        return self


class EventOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    application_id: UUID
    event_type: str
    occurred_at: datetime
    recorded_at: datetime
    notes: str | None


class DocumentInput(Input):
    kind: Literal["resume", "cover_letter"]
    label: str = Field(min_length=1, max_length=250)
    version_label: str | None = Field(default=None, max_length=100)
    storage_reference: str | None = Field(default=None, max_length=2000)


class DocumentPatch(Input):
    archived: bool


class DocumentOutput(DocumentInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
