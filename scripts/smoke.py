"""Synthetic end-to-end API smoke check against a disposable/local deployment."""

import argparse
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    with httpx.Client(
        base_url=args.base_url,
        timeout=20,
        headers={"X-Requested-With": "job-tracker", "Origin": args.base_url},
    ) as client:

        def call(method, path, data=None, status=200):
            response = client.request(method, f"/api/v1{path}", json=data)
            if response.status_code != status:
                raise RuntimeError(
                    f"{method} {path}: expected {status}, got {response.status_code}"
                )
            return response.json() if response.content else None

        assert call("GET", "/health/ready")["status"] == "ready"
        email = f"smoke-{uuid4().hex}@example.com"
        password = uuid4().hex + uuid4().hex
        call("POST", "/auth/register", {"email": email, "password": password}, 201)
        csrf = client.cookies.get("tracker_csrf") or client.cookies.get(
            "__Host-tracker_csrf"
        )
        client.headers["X-CSRF-Token"] = csrf
        if args.base_url.startswith("https://"):
            cookies = {cookie.name: cookie for cookie in client.cookies.jar}
            for name in ["__Host-tracker_session", "__Host-tracker_csrf"]:
                cookie = cookies[name]
                assert (
                    cookie.secure and cookie.path == "/" and not cookie.domain_specified
                )
                assert str(cookie._rest.get("SameSite", "")).lower() == "lax"
            assert "HttpOnly" in cookies["__Host-tracker_session"]._rest
            assert "HttpOnly" not in cookies["__Host-tracker_csrf"]._rest
        assert call("GET", "/auth/me")["email"] == email
        company = call("POST", "/companies", {"name": "Synthetic smoke company"}, 201)
        job = call(
            "POST",
            "/jobs",
            {
                "company_id": company["id"],
                "title": "Smoke engineer",
                "raw_description": "Required skills:\nPython and SQL\nPreferred skills:\nDocker",
            },
            201,
        )
        description = call("GET", f"/jobs/{job['id']}/descriptions")[0]
        analysis = call(
            "POST", f"/descriptions/{description['id']}/analyses", status=201
        )
        profile = call(
            "PUT", "/profile", {"revision": 0, "data": {"skills": ["Python", "SQL"]}}
        )
        match = call("POST", f"/analyses/{analysis['id']}/matches", status=201)
        assert match["profile_revision"] == profile["revision"]
        assert match["breakdown"]["score"] == 60
        now = datetime.now(UTC)
        application = call(
            "POST",
            "/applications",
            {
                "job_id": job["id"],
                "applied_on": (now - timedelta(days=1)).date().isoformat(),
            },
            201,
        )
        call(
            "POST",
            f"/applications/{application['id']}/events",
            {
                "event_type": "technical_interview",
                "occurred_at": (now - timedelta(minutes=1)).isoformat(),
            },
            201,
        )
        dashboard = call("GET", "/analytics/dashboard")
        assert dashboard["total"] == 1 and dashboard["interview_rate"]["value"] == 1
        call("POST", "/auth/logout", status=204)
        client.headers.pop("X-CSRF-Token")
        call("POST", "/auth/login", {"email": email, "password": password})
        assert call("GET", "/applications")["total"] == 1
        print(
            "Smoke passed: auth, CRUD, analysis, profile, matching, events, analytics, persistence."
        )
        print(
            "Synthetic records remain in the selected database; no existing records were modified."
        )


if __name__ == "__main__":
    main()
