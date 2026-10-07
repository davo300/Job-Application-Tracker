from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.entities import ApplicationEvent


@pytest.fixture
def tracker(auth_context):
    client, db, app = auth_context
    assert (
        client.post(
            "/api/v1/auth/register",
            json={"email": "tracker@example.com", "password": "long-tracker-passphrase"},
        ).status_code
        == 201
    )
    client.headers["X-CSRF-Token"] = client.cookies["tracker_csrf"]
    return client, db, app


def create_company(client, name="Example"):
    response = client.post("/api/v1/companies", json={"name": name, "location": "Detroit"})
    assert response.status_code == 201, response.text
    return response.json()


def create_job(client, company=None, **values):
    company = company or create_company(client)
    response = client.post(
        "/api/v1/jobs",
        json={
            "company_id": company["id"],
            "title": "Software Intern",
            "location": "Detroit",
            **values,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def apply(client, job, day="2026-10-05", **values):
    response = client.post(
        "/api/v1/applications", json={"job_id": job["id"], "applied_on": day, **values}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_company_crud_and_referenced_delete_conflict(tracker):
    client, _, _ = tracker
    company = create_company(client, "  Acme  ")
    assert company["name"] == "Acme"
    assert (
        client.patch(
            f"/api/v1/companies/{company['id']}", json={"notes": "Recruiter contact"}
        ).json()["notes"]
        == "Recruiter contact"
    )
    assert client.get(f"/api/v1/companies/{company['id']}").status_code == 200
    assert client.delete(f"/api/v1/companies/{company['id']}").status_code == 204
    assert client.get(f"/api/v1/companies/{company['id']}").status_code == 404
    job = create_job(client)
    assert client.delete(f"/api/v1/companies/{job['company_id']}").status_code == 409
    assert client.get(f"/api/v1/jobs/{job['id']}").status_code == 200


def test_job_edits_preserve_raw_description_versions(tracker):
    client, _, _ = tracker
    raw = "  Original requirements\nPython\n\n"
    job = create_job(client, raw_description=raw)
    path = f"/api/v1/jobs/{job['id']}"
    first = client.get(path + "/descriptions").json()
    assert first[0]["raw_text"] == raw
    assert (
        client.patch(
            path, json={"title": "Backend Intern", "raw_description": "New requirements"}
        ).status_code
        == 200
    )
    versions = client.get(path + "/descriptions").json()
    assert [item["version"] for item in versions] == [2, 1]
    assert versions[1]["raw_text"] == raw
    assert (
        client.post(path + "/descriptions", json={"raw_text": "New requirements"}).status_code
        == 200
    )
    assert len(client.get(path + "/descriptions").json()) == 2
    assert (
        client.patch(path, json={"title": "Should not save", "raw_description": ""}).status_code
        == 422
    )
    assert client.get(path).json()["title"] == "Backend Intern"


def test_partial_salary_validation_and_nullable_fields(tracker):
    client, _, _ = tracker
    job = create_job(
        client, salary_min="50000", salary_max="70000", salary_currency="USD", salary_period="year"
    )
    path = f"/api/v1/jobs/{job['id']}"
    assert client.patch(path, json={"salary_max": "40000"}).status_code == 422
    assert client.patch(path, json={"title": None}).status_code == 422
    assert client.patch(path, json={"company_id": None}).status_code == 422
    assert client.patch(path, json={"location": None}).json()["location"] is None
    assert client.get(path).json()["salary_max"] == "70000.00"


def test_archive_is_reversible_and_preserves_applications(tracker):
    client, _, _ = tracker
    job = create_job(client)
    application = apply(client, job)
    path = f"/api/v1/jobs/{job['id']}"
    assert client.delete(path).json()["archived_at"]
    assert client.get("/api/v1/jobs").json()["total"] == 0
    assert client.get("/api/v1/jobs?archived=true").json()["total"] == 1
    assert client.get(f"/api/v1/applications/{application['id']}").status_code == 200
    assert (
        client.post(
            "/api/v1/applications", json={"job_id": job["id"], "applied_on": "2026-10-05"}
        ).status_code
        == 409
    )
    assert client.patch(path, json={"archived": False}).json()["archived_at"] is None


def test_application_creates_initial_event_and_distinct_attempts(tracker):
    client, db, _ = tracker
    job = create_job(client)
    first = apply(client, job, notes="Tailored resume")
    second = apply(client, job)
    assert (first["attempt_number"], second["attempt_number"]) == (1, 2)
    events = list(
        db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == first["id"]))
    )
    assert len(events) == 1
    assert events[0].event_type == "applied"
    assert events[0].occurred_at == datetime(2026, 10, 5, tzinfo=UTC)
    path = f"/api/v1/applications/{first['id']}"
    assert client.patch(path, json={"notes": "Followed up"}).json()["notes"] == "Followed up"
    assert client.patch(path, json={"status": "offer"}).status_code == 422


def test_search_filters_sorting_and_pagination(tracker):
    client, _, _ = tracker
    company = create_company(client, "Zebra")
    jobs = [
        create_job(client, company, title=title)
        for title in ["Python Intern", "Backend Engineer", "100% Engineer"]
    ]
    for day, job in zip(["2026-09-01", "2026-10-01", "2026-10-05"], jobs, strict=True):
        apply(client, job, day)
    assert client.get("/api/v1/applications?q=python").json()["total"] == 1
    assert (
        client.get("/api/v1/applications?q=%25").json()["total"] == 1
    )  # percent is literal, not SQL wildcard
    assert (
        client.get(
            "/api/v1/applications?location=DETROIT&status=active&date_from=2026-10-01&date_to=2026-10-05"
        ).json()["total"]
        == 2
    )
    assert client.get("/api/v1/applications?status=offer").json()["total"] == 0
    assert client.get(f"/api/v1/applications?company_id={company['id']}").json()["total"] == 3
    result = client.get("/api/v1/applications?sort=oldest&page_size=1&page=2").json()
    assert result["total"] == 3
    assert result["items"][0]["applied_on"] == "2026-10-01"
    assert client.get("/api/v1/applications?sort=invalid").status_code == 422
    assert client.get("/api/v1/applications?page_size=101").status_code == 422
    assert (
        client.get("/api/v1/applications?date_from=2026-10-06&date_to=2026-10-01").status_code
        == 422
    )


def test_all_resources_are_private_and_cross_account_references_fail(tracker):
    client, _, app = tracker
    company = create_company(client)
    job = create_job(client, company)
    application = apply(client, job)
    with TestClient(app) as other:
        other.headers["X-Requested-With"] = "job-tracker"
        other.post(
            "/api/v1/auth/register",
            json={"email": "isolated@example.com", "password": "long-isolated-passphrase"},
        )
        other.headers["X-CSRF-Token"] = other.cookies["tracker_csrf"]
        for resource, record in [
            ("companies", company),
            ("jobs", job),
            ("applications", application),
        ]:
            assert other.get(f"/api/v1/{resource}").json()["total"] == 0
            assert other.get(f"/api/v1/{resource}/{record['id']}").status_code == 404
            assert other.patch(f"/api/v1/{resource}/{record['id']}", json={}).status_code == 404
        assert other.get(f"/api/v1/jobs/{job['id']}/descriptions").status_code == 404
        assert other.delete(f"/api/v1/jobs/{job['id']}").status_code == 404
        assert (
            other.post(
                "/api/v1/jobs", json={"company_id": company["id"], "title": "Forbidden"}
            ).status_code
            == 404
        )
        assert (
            other.post(
                "/api/v1/applications", json={"job_id": job["id"], "applied_on": "2026-10-05"}
            ).status_code
            == 404
        )
        own_company = create_company(other)
        own_job = create_job(other, own_company)
        assert (
            other.patch(
                f"/api/v1/jobs/{own_job['id']}", json={"company_id": company["id"]}
            ).status_code
            == 404
        )
    assert client.get("/api/v1/applications").json()["total"] == 1


def test_csrf_required_and_dangerous_urls_rejected(tracker):
    client, _, app = tracker
    assert (
        client.post(
            "/api/v1/companies", headers={"X-CSRF-Token": "wrong"}, json={"name": "No"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/companies", json={"name": "No", "website": "javascript:alert(1)"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/jobs",
            json={"company_id": str(uuid4()), "title": "No", "url": "file:///etc/passwd"},
        ).status_code
        == 422
    )
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/v1/applications").status_code == 401


def test_initial_event_failure_rolls_back_application(tracker, monkeypatch):
    client, _, _ = tracker
    job = create_job(client)

    def invalid_event(**values):
        return ApplicationEvent(**{**values, "occurred_at": None})

    monkeypatch.setattr("app.services.tracking.ApplicationEvent", invalid_event)
    response = client.post(
        "/api/v1/applications", json={"job_id": job["id"], "applied_on": "2026-10-05"}
    )
    assert response.status_code == 409
    assert client.get("/api/v1/applications").json()["total"] == 0


def test_blank_descriptions_and_incomplete_salaries_rejected(tracker):
    client, _, _ = tracker
    company = create_company(client)
    for values in [{"raw_description": "  \n "}, {"salary_min": "50000"}, {"title": " "}]:
        response = client.post(
            "/api/v1/jobs", json={"company_id": company["id"], "title": "Engineer", **values}
        )
        assert response.status_code == 422
    assert client.get("/api/v1/jobs").json()["total"] == 0
