from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace as Row

from app.api.analytics import summarize


def application(identifier, day, status="active", stage="applied"):
    return Row(id=identifier, applied_on=day, status=status, current_stage=stage)


def event(kind, time, identifier=1):
    return Row(id=identifier, event_type=kind, occurred_at=time, recorded_at=time)


def test_empty_ratios_are_unavailable():
    result = summarize([], None, None, "UTC")
    assert result["total"] == 0
    assert result["response_rate"]["value"] is None
    assert result["mean_response_days"] is None


def test_repeated_interviews_terminal_history_and_direct_offers():
    day = date(2026, 10, 5)
    start = datetime(2026, 10, 5, tzinfo=UTC)
    a = application(1, day, "rejected", "technical_interview")
    b = application(2, day, "offer")
    c = application(3, day)
    rows = [
        (a, event("applied", start)),
        (a, event("technical_interview", start + timedelta(days=1))),
        (a, event("technical_interview", start + timedelta(days=2))),
        (a, event("rejected", start + timedelta(days=3))),
        (b, event("offer", start + timedelta(days=2))),
        (c, None),
    ]
    result = summarize(rows, day, day, "UTC")
    assert result["interview_rate"] == {"numerator": 1, "denominator": 3, "value": 1 / 3}
    assert result["interview_to_offer"]["value"] == 0
    assert result["mean_response_days"] == 1.5
    assert result["unanswered"] == 1
    assert result["active_stages"]["applied"] == 1
    assert result["weekly_activity"] == [{"week": "2026-10-05", "applications": 3, "events": 0}]
    assert (
        next(d for d in result["stage_durations"] if d["stage"] == "technical_interview")[
            "completed_intervals"
        ]
        == 2
    )


def test_activity_timezone_and_cohort_are_independent():
    a = application(1, date(2026, 9, 1))
    e = event("note", datetime(2026, 10, 6, 1, tzinfo=UTC))
    result = summarize([(a, e)], date(2026, 10, 5), date(2026, 10, 5), "America/Detroit")
    assert result["total"] == 0
    assert result["weekly_activity"] == [{"week": "2026-10-05", "applications": 0, "events": 1}]


def test_endpoint_isolation_and_validation(auth_context):
    client, _, _ = auth_context
    assert client.get("/api/v1/analytics/dashboard").status_code == 401
    for email in ["analytics-one@example.com", "analytics-two@example.com"]:
        client.post(
            "/api/v1/auth/register", json={"email": email, "password": "analytics-test-passphrase"}
        )
        client.headers["X-CSRF-Token"] = client.cookies["tracker_csrf"]
        if email.startswith("analytics-one"):
            company = client.post("/api/v1/companies", json={"name": "Analytics"}).json()
            job = client.post(
                "/api/v1/jobs", json={"company_id": company["id"], "title": "Engineer"}
            ).json()
            client.post(
                "/api/v1/applications",
                json={"job_id": job["id"], "applied_on": datetime.now(UTC).date().isoformat()},
            )
            assert client.get("/api/v1/analytics/dashboard").json()["total"] == 1
        else:
            assert client.get("/api/v1/analytics/dashboard").json()["total"] == 0
    assert client.get("/api/v1/analytics/dashboard?timezone=Invalid/Zone").status_code == 422
    assert (
        client.get(
            "/api/v1/analytics/dashboard?date_from=2026-10-06&date_to=2026-10-05"
        ).status_code
        == 422
    )
