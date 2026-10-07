import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.entities import Application, ApplicationEvent, Company, Document, Job, User
from app.schemas.tracking import ApplicationInput, CompanyInput, EventInput, JobCreate
from app.services.tracking import TrackingError, TrackingService


@pytest.fixture
def history(auth_context):
    client, db, app = auth_context
    client.post(
        "/api/v1/auth/register",
        json={"email": "history@example.com", "password": "long-history-passphrase"},
    )
    client.headers["X-CSRF-Token"] = client.cookies["tracker_csrf"]
    company = client.post("/api/v1/companies", json={"name": "History Co"}).json()
    job = client.post(
        "/api/v1/jobs", json={"company_id": company["id"], "title": "Engineer"}
    ).json()
    base = (datetime.now(UTC) - timedelta(days=2)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    application = client.post(
        "/api/v1/applications", json={"job_id": job["id"], "applied_on": base.date().isoformat()}
    ).json()
    return client, db, app, application, base


def event(client, application, base, kind="recruiter_screen", **values):
    return client.post(
        f"/api/v1/applications/{application['id']}/events",
        json={"event_type": kind, "occurred_at": base.isoformat(), **values},
    )


def document(client, kind="resume"):
    response = client.post(
        "/api/v1/documents",
        json={
            "kind": kind,
            "label": "Backend resume",
            "version_label": "v1",
            "storage_reference": "resumes/backend-v1.pdf",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_transitions_preserve_history_and_outcome_retains_stage(history):
    client, _, _, application, base = history
    for offset, kind in enumerate(
        ["assessment", "technical_interview", "technical_interview", "final_interview", "offer"]
    ):
        result = event(client, application, base + timedelta(hours=offset), kind)
        assert result.status_code == 201
    current = result.json()
    assert current["current_stage"] == "final_interview"
    assert current["status"] == "offer"
    timeline = client.get(
        f"/api/v1/applications/{application['id']}/events?page_size=2&page=2"
    ).json()
    assert timeline["total"] == 6
    assert [item["event_type"] for item in timeline["items"]] == [
        "technical_interview",
        "technical_interview",
    ]
    assert event(client, application, base + timedelta(hours=6), "assessment").status_code == 409
    assert (
        event(
            client, application, base + timedelta(hours=6), "note", notes="Offer details saved"
        ).status_code
        == 201
    )
    assert client.get(f"/api/v1/applications/{application['id']}").json()["status"] == "offer"


def test_backdated_note_does_not_block_later_state_event(history):
    client, _, _, application, base = history
    assert (
        event(client, application, base + timedelta(hours=4), "note", notes="Follow-up").status_code
        == 201
    )
    assert event(client, application, base + timedelta(hours=1), "assessment").status_code == 201
    assert event(client, application, base, "technical_interview").status_code == 409
    assert (
        event(client, application, base + timedelta(hours=1), "technical_interview").status_code
        == 409
    )
    assert (
        event(client, application, base + timedelta(hours=2), "technical_interview").status_code
        == 201
    )


def test_invalid_event_times_and_empty_notes_rejected(history):
    client, _, _, application, base = history
    assert event(client, application, base - timedelta(days=1)).status_code == 422
    assert event(client, application, datetime.now(UTC) + timedelta(hours=1)).status_code == 422
    assert event(client, application, base.replace(tzinfo=None)).status_code == 422
    assert event(client, application, base, "note", notes="  ").status_code == 422
    assert event(client, application, base, "applied").status_code == 422
    assert client.get(f"/api/v1/applications/{application['id']}/events").json()["total"] == 1


def test_failed_event_insert_rolls_back_current_state(history, monkeypatch):
    client, db, _, application, base = history
    original_add = db.add

    def invalid_event_add(record):
        if isinstance(record, ApplicationEvent):
            record.occurred_at = None
        original_add(record)

    monkeypatch.setattr(db, "add", invalid_event_add)
    assert event(client, application, base, "offer").status_code == 409
    current = client.get(f"/api/v1/applications/{application['id']}").json()
    assert current["status"] == "active"
    assert current["current_stage"] == "applied"
    assert client.get(f"/api/v1/applications/{application['id']}/events").json()["total"] == 1


def test_document_references_kind_and_archiving(history):
    client, _, _, application, _ = history
    resume, cover = document(client), document(client, "cover_letter")
    path = f"/api/v1/applications/{application['id']}"
    assert client.patch(path, json={"resume_id": cover["id"]}).status_code == 422
    attached = client.patch(path, json={"resume_id": resume["id"], "cover_letter_id": cover["id"]})
    assert attached.status_code == 200
    assert attached.json()["resume_id"] == resume["id"]
    assert (
        client.patch(f"/api/v1/documents/{resume['id']}", json={"archived": True}).status_code
        == 200
    )
    assert client.get("/api/v1/documents?archived=true").json()["total"] == 1
    assert client.get(path).json()["resume_id"] == resume["id"]
    assert client.get(f"/api/v1/documents/{resume['id']}").json()["label"] == "Backend resume"
    assert client.patch(path, json={"resume_id": resume["id"]}).status_code == 200
    assert client.patch(path, json={"resume_id": None}).status_code == 200
    assert client.patch(path, json={"resume_id": resume["id"]}).status_code == 409
    assert (
        client.patch(
            f"/api/v1/documents/{resume['id']}", json={"label": "Changed", "archived": False}
        ).status_code
        == 422
    )
    client.patch(f"/api/v1/documents/{resume['id']}", json={"archived": False})
    assert client.patch(path, json={"resume_id": resume["id"]}).status_code == 200
    job = application["job"]
    created = client.post(
        "/api/v1/applications",
        json={
            "job_id": job["id"],
            "applied_on": application["applied_on"],
            "resume_id": resume["id"],
        },
    )
    assert created.status_code == 201
    assert created.json()["resume_id"] == resume["id"]


def test_document_metadata_and_events_are_database_immutable(history):
    client, db, _, application, _ = history
    resume = document(client)
    with pytest.raises(DBAPIError, match="immutable"), db.begin_nested():
        db.execute(
            update(Document)
            .where(Document.id == resume["id"])
            .values(storage_reference="overwritten.pdf")
        )
    with pytest.raises(DBAPIError, match="immutable"), db.begin_nested():
        db.execute(
            update(ApplicationEvent)
            .where(ApplicationEvent.application_id == application["id"])
            .values(notes="Overwritten")
        )


def test_history_and_documents_do_not_leak_across_accounts(history):
    client, _, app, application, base = history
    resume = document(client)
    with TestClient(app) as other:
        other.headers["X-Requested-With"] = "job-tracker"
        other.post(
            "/api/v1/auth/register",
            json={"email": "private-history@example.com", "password": "long-private-passphrase"},
        )
        other.headers["X-CSRF-Token"] = other.cookies["tracker_csrf"]
        assert other.get("/api/v1/documents").json()["total"] == 0
        assert other.get(f"/api/v1/documents/{resume['id']}").status_code == 404
        assert (
            other.patch(f"/api/v1/documents/{resume['id']}", json={"archived": True}).status_code
            == 404
        )
        assert other.get(f"/api/v1/applications/{application['id']}/events").status_code == 404
        assert event(other, application, base).status_code == 404
        company = other.post("/api/v1/companies", json={"name": "Other"}).json()
        job = other.post(
            "/api/v1/jobs", json={"company_id": company["id"], "title": "Other role"}
        ).json()
        assert (
            other.post(
                "/api/v1/applications",
                json={
                    "job_id": job["id"],
                    "applied_on": base.date().isoformat(),
                    "resume_id": resume["id"],
                },
            ).status_code
            == 404
        )


def test_concurrent_same_time_transitions_only_one_wins():
    """Separate committed connections exercise the real PostgreSQL row lock.

    Uses uniquely named disposable records, then deletes only those records.
    """
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required")
    engine = create_engine(url)
    owner = uuid4()
    job_id = app_id = company_id = None
    base = datetime.now(UTC) - timedelta(days=1)
    try:
        with Session(engine) as db:
            db.add(User(id=owner, email=f"{owner}@example.com", password_hash="test-only"))
            db.commit()
            service = TrackingService(db, owner)
            company = service.create_company(CompanyInput(name="Concurrent test"))
            company_id = company.id
            job = service.create_job(JobCreate(company_id=company_id, title="Concurrency test"))
            job_id = job.id
            application = service.create_application(
                ApplicationInput(job_id=job_id, applied_on=base.date())
            )
            app_id = application.id
        barrier = Barrier(2)

        def transition(kind):
            with Session(engine) as db:
                barrier.wait(timeout=10)
                try:
                    result = TrackingService(db, owner).record_event(
                        app_id, EventInput(event_type=kind, occurred_at=base)
                    )
                    return result.current_stage
                except TrackingError as exc:
                    return exc.status

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(transition, kind) for kind in ["assessment", "technical_interview"]
            ]
            results = [future.result(timeout=15) for future in futures]
        assert results.count(409) == 1
        with Session(engine) as db:
            actual = db.get(Application, app_id)
            assert actual.current_stage in results
            assert (
                len(
                    list(
                        db.scalars(
                            select(ApplicationEvent).where(
                                ApplicationEvent.application_id == app_id
                            )
                        )
                    )
                )
                == 2
            )
    finally:
        with Session(engine) as db:
            if app_id:
                db.execute(
                    delete(ApplicationEvent).where(ApplicationEvent.application_id == app_id)
                )
                db.execute(delete(Application).where(Application.id == app_id))
            if job_id:
                db.execute(delete(Job).where(Job.id == job_id))
            if company_id:
                db.execute(delete(Company).where(Company.id == company_id))
            db.execute(delete(User).where(User.id == owner))
            db.commit()
        engine.dispose()
