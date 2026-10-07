import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.main import create_app

HEADERS = {"X-Requested-With": "job-tracker", "Origin": "http://localhost:5173"}


@pytest.fixture
def auth_context():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required for authentication integration tests")
    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        app = create_app()
        app.dependency_overrides[get_session] = lambda: db
        with TestClient(app) as client:
            client.headers.update(HEADERS)
            yield client, db, app
        db.close()
        transaction.rollback()
    engine.dispose()
