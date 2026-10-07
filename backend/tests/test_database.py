"""Integration tests require a migrated, disposable PostgreSQL database.

Each test uses a rolled-back transaction; never point TEST_DATABASE_URL at a
production database. Schema lifecycle is verified separately by CI.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, insert, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models.entities import Application, Company, DescriptionVersion, Job, User


@pytest.fixture
def connection():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required for PostgreSQL integration tests")
    engine = create_engine(url)
    with engine.connect() as conn:
        tx = conn.begin()
        yield conn
        tx.rollback()
    engine.dispose()


def users(connection):
    ids = [uuid.uuid4(), uuid.uuid4()]
    for identifier in ids:
        connection.execute(
            insert(User).values(
                id=identifier, email=f"{identifier}@example.test", password_hash="test-hash"
            )
        )
    return ids


def job(connection):
    owner, other = users(connection)
    company, job_id = uuid.uuid4(), uuid.uuid4()
    connection.execute(insert(Company).values(id=company, user_id=owner, name="Example"))
    connection.execute(
        insert(Job).values(id=job_id, user_id=owner, company_id=company, title="Engineer")
    )
    return owner, other, company, job_id


def test_job_cannot_reference_another_users_company(connection):
    _, other, company, _ = job(connection)
    with pytest.raises(IntegrityError):
        connection.execute(insert(Job).values(user_id=other, company_id=company, title="Engineer"))


def test_application_cannot_reference_another_users_job(connection):
    _, other, _, job_id = job(connection)
    with pytest.raises(IntegrityError):
        connection.execute(
            insert(Application).values(user_id=other, job_id=job_id, applied_on="2026-10-05")
        )


def test_salary_bounds_rejected(connection):
    owner, _, company, _ = job(connection)
    with pytest.raises(IntegrityError):
        connection.execute(
            insert(Job).values(
                user_id=owner,
                company_id=company,
                title="Engineer",
                salary_min=100,
                salary_max=50,
                salary_currency="USD",
                salary_period="year",
            )
        )


def test_description_cannot_be_overwritten(connection):
    owner, _, _, job_id = job(connection)
    identifier = uuid.uuid4()
    connection.execute(
        insert(DescriptionVersion).values(
            id=identifier, user_id=owner, job_id=job_id, version=1, raw_text="Original requirements"
        )
    )
    with pytest.raises(DBAPIError, match="immutable"):
        connection.execute(
            update(DescriptionVersion)
            .where(DescriptionVersion.id == identifier)
            .values(raw_text="Replacement")
        )


def test_application_status_is_constrained(connection):
    owner, _, _, job_id = job(connection)
    with pytest.raises(IntegrityError):
        connection.execute(
            insert(Application).values(
                user_id=owner, job_id=job_id, applied_on="2026-10-05", status="made-up"
            )
        )
