from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.rate_limits import enforce_auth_attempt
from app.core.tokens import create_access_token, validate_jwt_settings
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


@router.get("/me", response_model=UserResponse)
def get_me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(user)


def _auth_response(user: User, settings: Settings) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id, settings),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )
