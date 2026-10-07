"""Authentication flows use real PostgreSQL and roll back after every test."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.database import get_session
from app.core.security import token_digest
from app.main import create_app
from app.models.entities import Session as LoginSession
from app.models.entities import User

PASSWORD = "a-long-private-passphrase"
HEADERS = {"X-Requested-With": "job-tracker", "Origin": "http://localhost:5173"}


def register(client, email="person@example.com"):
    return client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})


def test_registration_hashes_password_and_tokens(auth_context):
    client, db, _ = auth_context
    response = register(client, "  PERSON@EXAMPLE.COM ")
    assert response.status_code == 201
    assert response.json()["email"] == "person@example.com"
    assert set(response.json()) == {"id", "email", "created_at"}
    assert PASSWORD not in response.text
    user = db.scalar(select(User).where(User.email == "person@example.com"))
    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash != PASSWORD
    session = db.scalar(
        select(LoginSession).where(
            LoginSession.token_hash == token_digest(client.cookies["tracker_session"])
        )
    )
    assert session.token_hash == token_digest(client.cookies["tracker_session"])
    assert session.csrf_token_hash == token_digest(client.cookies["tracker_csrf"])
    cookies = response.headers.get_list("set-cookie")
    assert "HttpOnly" in cookies[0]
    assert "HttpOnly" not in cookies[1]
    assert all("SameSite=lax" in cookie and "Path=/" in cookie for cookie in cookies)
    assert response.headers["cache-control"] == "no-store"


def test_duplicate_email_does_not_break_existing_session(auth_context):
    client, _, _ = auth_context
    assert register(client).status_code == 201
    assert register(client, "PERSON@EXAMPLE.COM").status_code == 409
    assert client.get("/api/v1/auth/me").status_code == 200


def test_login_rotates_and_revokes_previous_session(auth_context):
    client, db, app = auth_context
    assert register(client).status_code == 201
    previous = client.cookies["tracker_session"]
    old_csrf = client.cookies["tracker_csrf"]
    result = client.post(
        "/api/v1/auth/login", json={"email": "PERSON@EXAMPLE.COM", "password": PASSWORD}
    )
    assert result.status_code == 200
    assert client.cookies["tracker_session"] != previous
    assert client.cookies["tracker_csrf"] != old_csrf
    assert (
        db.scalar(select(LoginSession).where(LoginSession.token_hash == token_digest(previous)))
        is None
    )
    with TestClient(app) as stale:
        stale.cookies.set("tracker_session", previous)
        assert stale.get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize("email", ["person@example.com", "unknown@example.com"])
def test_bad_credentials_have_same_error(auth_context, email):
    client, _, _ = auth_context
    register(client)
    result = client.post("/api/v1/auth/login", json={"email": email, "password": "incorrect"})
    assert result.status_code == 401
    assert result.json() == {"detail": "Invalid email or password"}


def test_me_is_scoped_to_session_not_supplied_user_id(auth_context):
    client, _, app = auth_context
    first = register(client).json()
    with TestClient(app) as other:
        other.headers.update(HEADERS)
        second = register(other, "other@example.com").json()
        assert first["id"] != second["id"]
        assert other.get(f"/api/v1/auth/me?user_id={first['id']}").json()["id"] == second["id"]
    assert client.get("/api/v1/auth/me").json()["id"] == first["id"]


def test_logout_requires_csrf_and_revokes_session(auth_context):
    client, db, app = auth_context
    register(client)
    token = client.cookies["tracker_session"]
    csrf = client.cookies["tracker_csrf"]
    for headers in [{}, {"X-CSRF-Token": "wrong"}]:
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 403
        assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert not client.cookies.get("tracker_session")
    assert not client.cookies.get("tracker_csrf")
    assert (
        db.scalar(select(LoginSession).where(LoginSession.token_hash == token_digest(token)))
        is None
    )
    with TestClient(app) as stale:
        stale.cookies.set("tracker_session", token)
        assert stale.get("/api/v1/auth/me").status_code == 401


def test_csrf_token_from_another_session_is_rejected(auth_context):
    client, _, app = auth_context
    register(client)
    with TestClient(app) as other:
        other.headers.update(HEADERS)
        register(other, "other@example.com")
        wrong = other.cookies["tracker_csrf"]
        assert (
            client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": wrong}).status_code == 403
        )


def test_expired_session_is_rejected(auth_context):
    client, db, _ = auth_context
    register(client)
    db.execute(update(LoginSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_no_cookie_and_forged_cookie_are_rejected(auth_context):
    client, _, _ = auth_context
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.set("tracker_session", "forged")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_production_cookies_are_secure_and_host_scoped(auth_context):
    from app.core.config import Settings

    _, db, _ = auth_context
    settings = Settings(environment="production", allowed_origins=["https://tracker.example.com"])
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: db
    with TestClient(app, base_url="https://tracker.example.com") as client:
        client.headers.update(
            {"X-Requested-With": "job-tracker", "Origin": "https://tracker.example.com"}
        )
        response = register(client)
        assert response.status_code == 201
        cookies = response.headers.get_list("set-cookie")
        assert all("Secure" in cookie and "Domain=" not in cookie for cookie in cookies)
        assert client.cookies.get("__Host-tracker_session")
        assert client.get("/api/v1/auth/me").status_code == 200
        csrf = client.cookies["__Host-tracker_csrf"]
        assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
        assert not client.cookies.get("__Host-tracker_session")


def test_login_upgrades_old_password_hash_parameters(auth_context):
    from argon2 import PasswordHasher

    from app.core.security import hasher

    client, db, _ = auth_context
    register(client)
    user = db.scalar(select(User).where(User.email == "person@example.com"))
    old_hash = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(PASSWORD)
    user.password_hash = old_hash
    db.commit()
    result = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert result.status_code == 200
    db.refresh(user)
    assert user.password_hash != old_hash
    assert not hasher.check_needs_rehash(user.password_hash)
