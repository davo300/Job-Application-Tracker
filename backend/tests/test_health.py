from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.database import get_session
from app.main import create_app


def test_liveness_does_not_need_database():
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health/live").json() == {"status": "ok"}


def test_readiness_requires_current_migration():
    app = create_app()
    session = Mock()
    session.execute.return_value.scalar_one.return_value = "0002_document_versions"
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        assert client.get("/api/v1/health/ready").status_code == 200
        session.execute.return_value.scalar_one.return_value = "outdated"
        assert client.get("/api/v1/health/ready").status_code == 503


def test_database_error_is_sanitized():
    app = create_app()
    session = Mock()
    session.execute.side_effect = OperationalError("secret query", {}, Exception("password"))
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert "password" not in response.text
        assert "secret query" not in response.text
