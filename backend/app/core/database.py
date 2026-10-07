from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def build_engine(database_url: str):
    # Engine construction is lazy: no connection until a query is issued.
    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


def get_session(request: Request):
    with Session(request.app.state.engine) as session:
        yield session
