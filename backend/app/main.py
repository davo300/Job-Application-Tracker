import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.health import router
from app.api.tracking import router as tracking_router
from app.core.config import Settings, get_settings
from app.core.database import build_engine
from app.core.http_security import install_security
from app.services.tracking import TrackingError


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    yield
    app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Job Application Tracker",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    app.state.engine = build_engine(settings.database_url)
    app.dependency_overrides[get_settings] = lambda: settings
    install_security(app, settings)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # FastAPI's default response includes raw input, including passwords.
        errors = [
            {"loc": error["loc"], "type": error["type"], "msg": "Invalid value"}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(TrackingError)
    async def tracking_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

    app.include_router(tracking_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
