from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from app.analysis.extraction import DeterministicProvider, Extraction, validate_evidence
from app.models.entities import JobAnalysis
from app.services.analysis import AnalysisService
from app.services.tracking import TrackingError


def test_parser_evidence_sections_boundaries_and_unicode():
    text = "Company: Élan Labs\r\nTitle: Backend Engineer\r\nLocation: Toronto\r\nRequired skills:\r\n• Python, C++, C# and PostgreSQL\r\nPreferred skills:\r\nReact.js and AWS\r\nResponsibilities:\r\nBuild REST APIs\r\nQualifications:\r\nBachelor degree and 2+ years experience\r\nJavaScript, not JavaBeans\r\n"
    result = DeterministicProvider().extract(text)
    validate_evidence(result, text)
    assert result.company.value == "Élan Labs"
    assert {e.value for e in result.required_skills} == {
        "Python",
        "C++",
        "C#",
        "PostgreSQL",
    }
    assert {e.value for e in result.preferred_skills} == {"React", "AWS"}
    assert "Java" not in {e.value for e in result.keywords}
    assert result.responsibilities[0].value == "Build REST APIs"
    assert len(result.education) == len(result.experience) == 1


def test_unknown_and_negated_requirements_are_not_required():
    result = DeterministicProvider().extract(
        "Requirements:\nPython not required\nBenefits:\nJava community\nGo to our website\n"
    )
    assert not result.required_skills
    assert {e.value for e in result.other_skills} == {"Python", "Java"}
    assert result.title is None
    assert DeterministicProvider().extract("").keywords == []


def test_invalid_evidence_rejected():
    result = Extraction.model_validate(
        {"title": {"value": "Engineer", "quote": "Fake", "start": 0, "end": 4}}
    )
    with pytest.raises(ValueError):
        validate_evidence(result, "Real")


def test_analysis_api_preserves_versions_and_isolates_users(auth_context):
    client, db, _ = auth_context
    assert (
        client.post(
            "/api/v1/descriptions/00000000-0000-0000-0000-000000000000/analyses"
        ).status_code
        == 401
    )
    user = client.post(
        "/api/v1/auth/register",
        json={"email": "analysis@example.com", "password": "analysis-test-passphrase"},
    ).json()
    client.headers["X-CSRF-Token"] = client.cookies["tracker_csrf"]
    company = client.post("/api/v1/companies", json={"name": "Extraction"}).json()
    job = client.post(
        "/api/v1/jobs",
        json={
            "company_id": company["id"],
            "title": "Engineer",
            "raw_description": "Required skills:\nPython and SQL",
        },
    ).json()
    versions = client.get(f"/api/v1/jobs/{job['id']}/descriptions").json()
    path = f"/api/v1/descriptions/{versions[0]['id']}/analyses"
    first = client.post(path)
    assert first.status_code == 201, first.text
    assert client.post(path).json()["id"] == first.json()["id"]
    assert client.post(path).status_code == 200
    assert client.get(path).json()["total"] == 1
    client.post(
        f"/api/v1/jobs/{job['id']}/descriptions", json={"raw_text": "Preferred skills:\nReact"}
    )
    newer = client.get(f"/api/v1/jobs/{job['id']}/descriptions").json()[0]
    assert client.post(f"/api/v1/descriptions/{newer['id']}/analyses").status_code == 201
    assert (
        client.get(path).json()["items"][0]["structured_data"]["required_skills"][0]["value"]
        == "Python"
    )
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            update(JobAnalysis)
            .where(JobAnalysis.id == UUID(first.json()["id"]))
            .values(provider_version="tampered")
        )
    provider = DeterministicProvider()
    provider.version = "test-new-version"
    row, created = AnalysisService(db, UUID(user["id"]), provider).create(UUID(versions[0]["id"]))
    assert created and row.provider_version == "test-new-version"
    assert (
        db.scalar(
            select(JobAnalysis).where(JobAnalysis.id == UUID(first.json()["id"]))
        ).provider_version
        == "1.0.1"
    )
    client.post(
        "/api/v1/auth/register",
        json={"email": "analysis-other@example.com", "password": "analysis-test-passphrase"},
    )
    client.headers["X-CSRF-Token"] = client.cookies["tracker_csrf"]
    assert client.get(path).status_code == 404
    assert client.post(path).status_code == 404


def test_invalid_provider_output_does_not_persist(auth_context):
    client, db, _ = auth_context
    user = client.post(
        "/api/v1/auth/register",
        json={"email": "bad-analysis@example.com", "password": "analysis-test-passphrase"},
    ).json()
    client.headers["X-CSRF-Token"] = client.cookies["tracker_csrf"]
    company = client.post("/api/v1/companies", json={"name": "Invalid"}).json()
    job = client.post(
        "/api/v1/jobs",
        json={"company_id": company["id"], "title": "Engineer", "raw_description": "Real"},
    ).json()
    version = client.get(f"/api/v1/jobs/{job['id']}/descriptions").json()[0]

    class BadProvider:
        name = "invalid"
        version = "1"

        def extract(self, text):
            return {"title": {"value": "Fake", "quote": "Fake", "start": 0, "end": 4}}

    with pytest.raises(TrackingError) as error:
        AnalysisService(db, UUID(user["id"]), BadProvider()).create(UUID(version["id"]))
    assert error.value.status == 502
    assert client.get(f"/api/v1/descriptions/{version['id']}/analyses").json()["total"] == 0


def test_mixed_inline_requirements_stay_unclassified():
    result = DeterministicProvider().extract("Required: Python. Preferred: Docker.")
    assert not result.required_skills and not result.preferred_skills
    assert {e.value for e in result.other_skills} == {"Python", "Docker"}
