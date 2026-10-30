from uuid import UUID

import pytest
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError

from app.analysis.extraction import Extraction
from app.matching.scoring import ProfileData, score
from app.models.entities import MatchResult


def extraction(required=(), preferred=()):
    def items(values):
        return [{"value": value, "quote": value, "start": 0, "end": len(value)} for value in values]

    return Extraction(required_skills=items(required), preferred_skills=items(preferred))


def test_weighted_evidence_dedup_aliases_and_missing():
    profile = ProfileData(
        skills=[" PYTHON ", "Postgres"], projects=[{"name": "API", "skills": ["python"]}]
    )
    result = score(profile, extraction(["Python", "PostgreSQL", "Python"], ["React", "Python"]))
    assert result["score"] == 63.3
    assert result["components"][0]["matched"] == ["PostgreSQL", "Python"]
    assert result["components"][1]["missing"] == ["React"]
    assert result["relevant_projects"][0]["matched_skills"] == ["Python"]


def test_unknown_requirements_and_empty_profile():
    assert score(ProfileData(), extraction())["score"] is None
    result = score(ProfileData(), extraction(["Python"]))
    assert result["score"] == 0
    assert result["scored_weight"] == pytest.approx(0.8)
    assert result["components"][1]["value"] is None


def test_project_and_experience_tags_supply_evidence():
    profile = ProfileData(
        projects=[{"name": "API", "skills": ["Python"]}],
        experience=[{"name": "Internship", "skills": ["Python"]}],
    )
    assert score(profile, extraction(["Python"]))["score"] == 100
    assert score(profile, extraction(["Java"]))["score"] == 0


def test_profile_revisions_matches_snapshots_and_isolation(auth_context):
    client, db, _ = auth_context
    assert client.get("/api/v1/profile").status_code == 401
    client.post(
        "/api/v1/auth/register",
        json={"email": "matching@example.com", "password": "matching-test-passphrase"},
    )
    client.headers["X-CSRF-Token"] = client.cookies["tracker_csrf"]
    assert client.get("/api/v1/profile").json() is None
    company = client.post("/api/v1/companies", json={"name": "Match"}).json()
    job = client.post(
        "/api/v1/jobs",
        json={
            "company_id": company["id"],
            "title": "Engineer",
            "raw_description": "Required skills:\nPython",
        },
    ).json()
    description = client.get(f"/api/v1/jobs/{job['id']}/descriptions").json()[0]
    analysis = client.post(f"/api/v1/descriptions/{description['id']}/analyses").json()
    path = f"/api/v1/analyses/{analysis['id']}/matches"
    assert client.post(path).status_code == 409
    first = client.put("/api/v1/profile", json={"revision": 0, "data": {"skills": ["Python"]}})
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 1
    match = client.post(path)
    assert match.status_code == 201, match.text
    old = match.json()
    assert old["breakdown"]["score"] == 75
    assert (
        client.put(
            "/api/v1/profile", json={"revision": 0, "data": {"skills": ["Java"]}}
        ).status_code
        == 409
    )
    second = client.put("/api/v1/profile", json={"revision": 1, "data": {"skills": ["Java"]}})
    assert second.json()["revision"] == 2
    assert client.post(path).json()["breakdown"]["score"] == 0
    records = client.get(path).json()
    assert records["total"] == 2
    saved = next(r for r in records["items"] if r["id"] == old["id"])
    assert saved["input_snapshot"]["profile"]["skills"] == ["Python"]
    assert saved["profile_revision"] == 1
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            update(MatchResult)
            .where(MatchResult.id == UUID(old["id"]))
            .values(scorer_version="tampered")
        )
    client.post(
        "/api/v1/auth/register",
        json={"email": "matching-other@example.com", "password": "matching-test-passphrase"},
    )
    client.headers["X-CSRF-Token"] = client.cookies["tracker_csrf"]
    assert client.get("/api/v1/profile").json() is None
    assert client.get(path).status_code == 404
    assert client.post(path).status_code == 404
    assert (
        client.put(
            "/api/v1/profile",
            json={"revision": 0, "data": {"projects": [{"name": " ", "skills": [""]}]}},
        ).status_code
        == 422
    )
