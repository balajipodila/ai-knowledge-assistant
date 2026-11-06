from secrets import token_urlsafe
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.demo import ensure_demo_mode, is_demo_user
from app.core.rate_limits import enforce_auth_attempt, enforce_demo_session_attempt
from app.core.tokens import create_access_token, validate_jwt_settings
from app.models.document import Document
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, SignupRequest, UserResponse
from app.services.auth import (
    AuthService,
    DuplicateEmailError,
    InvalidCredentialsError,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    http_request: Request,
    request: SignupRequest,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthResponse:
    if not settings.signup_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signups are temporarily unavailable. Please try the demo instead.",
        )
    if str(request.email).strip().lower() == settings.demo_user_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email address is reserved.",
        )
    if settings.demo_mode:
        user_count = session.scalar(select(func.count(User.id))) or 0
        document_count = session.scalar(select(func.count(Document.id))) or 0
        if user_count >= settings.demo_max_users:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The public demo has reached its user limit.",
            )
        if document_count >= settings.demo_max_documents:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The public demo has reached its document limit.",
            )
    enforce_auth_attempt(
        http_request,
        email=str(request.email),
        action="signup",
        settings=settings,
    )
    validate_jwt_settings(settings)
    try:
        user = AuthService().signup(
            session,
            email=str(request.email),
            password=request.password.get_secret_value(),
        )
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from None

    return _auth_response(user, settings)


@router.post("/login", response_model=AuthResponse)
def login(
    http_request: Request,
    request: LoginRequest,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthResponse:
    enforce_auth_attempt(
        http_request,
        email=str(request.email),
        action="login",
        settings=settings,
    )
    validate_jwt_settings(settings)
    try:
        user = AuthService().login(
            session,
            email=str(request.email),
            password=request.password.get_secret_value(),
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return _auth_response(user, settings)


@router.post("/demo", response_model=AuthResponse)
def demo_session(
    http_request: Request,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthResponse:
    ensure_demo_mode(settings)
    enforce_demo_session_attempt(http_request, settings)
    validate_jwt_settings(settings)
    user = session.scalar(
        select(User).where(func.lower(func.trim(User.email)) == settings.demo_user_email)
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The demo is being prepared. Please try again later.",
        )
    return _auth_response(
        user,
        settings,
        rate_limit_identity=f"demo:{token_urlsafe(18)}",
        is_demo=True,
        expires_minutes=settings.demo_session_expire_minutes,
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserResponse:
    return _user_response(user, settings)


def _auth_response(
    user: User,
    settings: Settings,
    *,
    rate_limit_identity: str | None = None,
    is_demo: bool = False,
    expires_minutes: int | None = None,
) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(
            user.id,
            settings,
            rate_limit_identity=rate_limit_identity,
            is_demo=is_demo,
            expires_minutes=expires_minutes,
        ),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=_user_response(user, settings),
    )


def _user_response(user: User, settings: Settings) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        is_demo=is_demo_user(user, settings),
    )
