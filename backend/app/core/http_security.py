"""Same-origin request checks protect pre-login flows; CSRF tokens protect sessions.

No CORS middleware is enabled. Requiring a custom header prevents simple
cross-origin form requests, including when an Origin header is absent.
"""

from fastapi import Request
from starlette.responses import JSONResponse

from app.core.config import Settings
from app.core.rate_limit import AuthRateLimiter


def install_security(app, settings: Settings) -> None:
    limiter = AuthRateLimiter(attempts=settings.auth_rate_limit)
    app.state.auth_limiter = limiter

    def secure_response(response, request):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if (
                request.headers.get("x-requested-with") != "job-tracker"
                or (origin is not None and origin not in settings.allowed_origins)
                or request.headers.get("sec-fetch-site") == "cross-site"
            ):
                return secure_response(
                    JSONResponse(status_code=403, content={"detail": "Request origin rejected"}),
                    request,
                )
        if request.method == "POST" and request.url.path.rstrip("/") in {
            "/api/v1/auth/login",
            "/api/v1/auth/register",
        }:
            host = request.client.host if request.client else "unknown"
            if not limiter.allow(host):
                return secure_response(
                    JSONResponse(
                        status_code=429,
                        content={"detail": "Too many attempts; try again later"},
                        headers={"Retry-After": "60"},
                    ),
                    request,
                )
        return secure_response(await call_next(request), request)
