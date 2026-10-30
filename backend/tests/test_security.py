import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.rate_limit import AuthRateLimiter
from app.core.security import hasher, token_digest, verify_password
from app.main import create_app
from app.schemas.auth import RegisterInput


def test_password_hashes_are_salted_and_verifiable():
    password = "a-long-private-passphrase"
    first, second = hasher.hash(password), hasher.hash(password)
    assert first != second
    assert first.startswith("$argon2id$")
    assert verify_password(first, password)
    assert not verify_password(first, "wrong-password")
    assert not verify_password("not-a-valid-hash", password)


def test_registration_validation_and_secret_representation():
    data = RegisterInput(email="  PERSON@EXAMPLE.COM ", password="a-long-private-passphrase")
    assert data.email == "person@example.com"
    assert "a-long-private-passphrase" not in repr(data)
    for password in ["too-short", "x" * 129]:
        with pytest.raises(ValidationError):
            RegisterInput(email="person@example.com", password=password)


def test_production_requires_https_origins():
    with pytest.raises(ValidationError):
        Settings(environment="production")
    settings = Settings(environment="production", allowed_origins=["https://tracker.example.com"])
    assert settings.session_cookie_name.startswith("__Host-")
    assert settings.csrf_cookie_name.startswith("__Host-")


def test_throttle_bounds_and_expiry(monkeypatch):
    clock = [1.0]
    monkeypatch.setattr("app.core.rate_limit.monotonic", lambda: clock[0])
    limiter = AuthRateLimiter(attempts=2, window=60, max_clients=1)
    assert limiter.allow("one")
    assert limiter.allow("one")
    assert not limiter.allow("one")
    assert not limiter.allow("two")
    clock[0] = 62.0
    assert limiter.allow("two")


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Requested-With": "job-tracker", "Origin": "https://attacker.example"},
        {"X-Requested-With": "job-tracker", "Sec-Fetch-Site": "cross-site"},
        {"X-Requested-With": "job-tracker", "Origin": "null"},
    ],
)
def test_prelogin_cross_site_requests_rejected_without_database(headers):
    with TestClient(create_app()) as client:
        assert client.post("/api/v1/auth/login", headers=headers, json={}).status_code == 403


def test_validation_does_not_echo_password():
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/auth/register",
            headers={"X-Requested-With": "job-tracker"},
            json={"email": "invalid", "password": "secret"},
        )
        assert response.status_code == 422
        assert "secret" not in response.text
        assert "input" not in response.text
        assert response.headers["cache-control"] == "no-store"


def test_login_throttle_returns_retry_after():
    app = create_app()
    app.state.auth_limiter.attempts = 1
    with TestClient(app) as client:
        headers = {"X-Requested-With": "job-tracker"}
        assert client.post("/api/v1/auth/login", headers=headers, json={}).status_code == 422
        result = client.post("/api/v1/auth/login", headers=headers, json={})
        assert result.status_code == 429
        assert result.headers["retry-after"] == "60"


def test_token_digest_does_not_store_raw_token():
    digest = token_digest("private-session-token")
    assert len(digest) == 64
    assert "private-session-token" not in digest


def test_app_factory_uses_its_own_database_configuration():
    settings = Settings(database_url="postgresql+psycopg://example:password@localhost/custom_db")
    app = create_app(settings)
    assert app.state.engine.url.database == "custom_db"
    with TestClient(app) as client:
        assert client.get("/api/v1/health/live").status_code == 200


def test_security_headers_include_rejected_requests():
    with TestClient(create_app()) as client:
        for response in [
            client.get("/api/v1/health/live"),
            client.post("/api/v1/auth/login", json={}),
        ]:
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["x-frame-options"] == "DENY"
            assert response.headers["referrer-policy"] == "no-referrer"
