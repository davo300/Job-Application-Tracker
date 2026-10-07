"""Operational schema. Ownership FKs prevent cross-account references.

JSONB is reserved for versioned analysis/profile data; searchable operational
fields remain relational. Services will control transactions and state changes.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Identity:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Identity, Timestamps, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    __table_args__ = (CheckConstraint("email = lower(trim(email))", name="email_normalized"),)


class Company(Identity, Timestamps, Base):
    __tablename__ = "companies"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(250))
    website: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(250))
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        CheckConstraint("length(trim(name)) > 0", name="name_nonempty"),
    )


class Job(Identity, Timestamps, Base):
    __tablename__ = "jobs"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(250))
    work_arrangement: Mapped[str | None] = mapped_column(String(20))
    employment_type: Mapped[str | None] = mapped_column(String(30))
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    salary_period: Mapped[str | None] = mapped_column(String(20))
    posted_on: Mapped[date | None] = mapped_column(Date)
    deadline_on: Mapped[date | None] = mapped_column(Date)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        ForeignKeyConstraint(["company_id", "user_id"], ["companies.id", "companies.user_id"]),
        CheckConstraint("length(trim(title)) > 0", name="title_nonempty"),
        CheckConstraint(
            "work_arrangement IN ('remote','hybrid','on_site')", name="work_arrangement"
        ),
        CheckConstraint(
            "employment_type IN ('full_time','part_time','internship','contract','temporary','other')",
            name="employment_type",
        ),
        CheckConstraint(
            "salary_min >= 0 AND salary_max >= 0 AND salary_max >= salary_min", name="salary_bounds"
        ),
        CheckConstraint("salary_period IN ('hour','month','year')", name="salary_period"),
        CheckConstraint(
            "(salary_min IS NULL AND salary_max IS NULL) OR (salary_currency IS NOT NULL AND salary_period IS NOT NULL)",
            name="salary_units",
        ),
        CheckConstraint("salary_currency ~ '^[A-Z]{3}$'", name="currency_format"),
    )


class DescriptionVersion(Identity, Base):
    __tablename__ = "job_description_versions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(index=True)
    version: Mapped[int]
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        ForeignKeyConstraint(["job_id", "user_id"], ["jobs.id", "jobs.user_id"]),
        UniqueConstraint("job_id", "version"),
        CheckConstraint("version > 0", name="positive_version"),
    )


class JobAnalysis(Identity, Base):
    __tablename__ = "job_analyses"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    description_version_id: Mapped[uuid.UUID] = mapped_column(index=True)
    provider: Mapped[str] = mapped_column(String(100))
    provider_version: Mapped[str] = mapped_column(String(100))
    schema_version: Mapped[int]
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        ForeignKeyConstraint(
            ["description_version_id", "user_id"],
            ["job_description_versions.id", "job_description_versions.user_id"],
        ),
        CheckConstraint("schema_version > 0", name="positive_schema_version"),
    )


class Document(Identity, Timestamps, Base):
    __tablename__ = "documents"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    label: Mapped[str] = mapped_column(String(250))
    version_label: Mapped[str | None] = mapped_column(String(100))
    storage_reference: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        CheckConstraint("kind IN ('resume','cover_letter')", name="kind"),
    )


class Application(Identity, Timestamps, Base):
    __tablename__ = "applications"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    job_id: Mapped[uuid.UUID] = mapped_column(index=True)
    attempt_number: Mapped[int] = mapped_column(default=1, server_default="1")
    applied_on: Mapped[date] = mapped_column(Date)
    current_stage: Mapped[str] = mapped_column(
        String(30), default="applied", server_default="applied"
    )
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    resume_id: Mapped[uuid.UUID | None]
    cover_letter_id: Mapped[uuid.UUID | None]
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(["job_id", "user_id"], ["jobs.id", "jobs.user_id"]),
        ForeignKeyConstraint(["resume_id", "user_id"], ["documents.id", "documents.user_id"]),
        ForeignKeyConstraint(["cover_letter_id", "user_id"], ["documents.id", "documents.user_id"]),
        UniqueConstraint("user_id", "job_id", "attempt_number"),
        CheckConstraint("attempt_number > 0", name="positive_attempt"),
        CheckConstraint("status IN ('active','offer','rejected','withdrawn')", name="status"),
        CheckConstraint(
            "current_stage IN ('applied','assessment','recruiter_screen','technical_interview','behavioral_interview','final_interview')",
            name="stage",
        ),
        Index("ix_applications_user_status", "user_id", "status"),
        Index("ix_applications_user_date", "user_id", "applied_on"),
    )


class ApplicationEvent(Identity, Base):
    __tablename__ = "application_events"
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"))
    event_type: Mapped[str] = mapped_column(String(30))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('applied','assessment','recruiter_screen','technical_interview','behavioral_interview','final_interview','offer','rejected','withdrawn','note')",
            name="event_type",
        ),
        Index("ix_events_application_time", "application_id", "occurred_at"),
    )


class Profile(Identity, Timestamps, Base):
    __tablename__ = "profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        CheckConstraint("revision > 0", name="positive_revision"),
    )


class MatchResult(Identity, Base):
    __tablename__ = "match_results"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(index=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)
    profile_revision: Mapped[int]
    scorer_version: Mapped[str] = mapped_column(String(100))
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(
            ["analysis_id", "user_id"], ["job_analyses.id", "job_analyses.user_id"]
        ),
        ForeignKeyConstraint(["profile_id", "user_id"], ["profiles.id", "profiles.user_id"]),
        CheckConstraint("profile_revision > 0", name="positive_profile_revision"),
    )


class Session(Identity, Base):
    __tablename__ = "sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
