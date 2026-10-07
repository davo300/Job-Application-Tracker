from fastapi import APIRouter, HTTPException, Request, Response

from app.api.dependencies import Configuration, CurrentUser, Service
from app.schemas.auth import LoginInput, RegisterInput, UserOutput
from app.services.auth import AccountExists, InvalidCredentials, IssuedSession

router = APIRouter(prefix="/auth", tags=["authentication"])


def set_cookies(response: Response, issued: IssuedSession, settings) -> None:
    for name, value, http_only in (
        (settings.session_cookie_name, issued.token, True),
        (settings.csrf_cookie_name, issued.csrf_token, False),
    ):
        response.set_cookie(
            name,
            value,
            max_age=settings.session_ttl_hours * 3600,
            httponly=http_only,
            secure=settings.environment == "production",
            samesite="lax",
            path="/",
        )


@router.post("/register", response_model=UserOutput, status_code=201)
def register(
    data: RegisterInput,
    request: Request,
    response: Response,
    service: Service,
    settings: Configuration,
):
    try:
        issued = service.register(
            str(data.email),
            data.password.get_secret_value(),
            request.cookies.get(settings.session_cookie_name),
        )
    except AccountExists:
        raise HTTPException(status_code=409, detail="Account could not be created") from None
    set_cookies(response, issued, settings)
    return issued.user


@router.post("/login", response_model=UserOutput)
def login(
    data: LoginInput,
    request: Request,
    response: Response,
    service: Service,
    settings: Configuration,
):
    try:
        issued = service.login(
            str(data.email),
            data.password.get_secret_value(),
            request.cookies.get(settings.session_cookie_name),
        )
    except InvalidCredentials:
        raise HTTPException(status_code=401, detail="Invalid email or password") from None
    set_cookies(response, issued, settings)
    return issued.user


@router.get("/me", response_model=UserOutput)
def me(auth: CurrentUser):
    return auth.user


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    auth: CurrentUser,
    service: Service,
    settings: Configuration,
):
    service.logout(request.cookies[settings.session_cookie_name])
    for name in (settings.session_cookie_name, settings.csrf_cookie_name):
        response.delete_cookie(
            name,
            path="/",
            secure=settings.environment == "production",
            httponly=name == settings.session_cookie_name,
            samesite="lax",
        )
