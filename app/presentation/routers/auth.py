"""
Auth router — presentation layer only.
No business logic here; delegates entirely to AuthService.
"""

from app.application.services.auth_service import AuthError, AuthService
from app.dependencies import get_client_ip, get_current_user, get_user_agent
from app.domain.entities.user import User
from app.infrastructure.database import get_db_session
from app.presentation.schemas.auth_schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserProfileResponse,
)
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["Authentication"])
_bearer = HTTPBearer(auto_error=False)


def _get_auth_service(session: AsyncSession = Depends(get_db_session)) -> AuthService:
    return AuthService(
        user_repo=UserRepository(session),
        token_repo=RefreshTokenRepository(session),
    )


@router.post(
    "/register",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    body: RegisterRequest,
    service: AuthService = Depends(_get_auth_service),
):
    try:
        user = await service.register(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
        )
        return UserProfileResponse.model_validate(user)
    except AuthError as e:
        if e.code == "EMAIL_TAKEN":
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive token pair",
)
async def login(
    body: LoginRequest,
    request: Request,
    service: AuthService = Depends(_get_auth_service),
):
    ip = get_client_ip(request)
    ua = get_user_agent(request)
    try:
        access_token, refresh_token = await service.login(
            email=body.email,
            password=body.password,
            ip_address=ip,
            user_agent=ua,
        )
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except AuthError as e:
        code_map = {
            "RATE_LIMITED": status.HTTP_429_TOO_MANY_REQUESTS,
            "ACCOUNT_LOCKED": status.HTTP_423_LOCKED,
            "ACCOUNT_SUSPENDED": status.HTTP_403_FORBIDDEN,
            "ACCOUNT_BANNED": status.HTTP_403_FORBIDDEN,
        }
        http_status = code_map.get(e.code, status.HTTP_401_UNAUTHORIZED)
        raise HTTPException(http_status, detail=str(e))


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and issue new access token",
)
async def refresh(
    body: RefreshRequest,
    request: Request,
    service: AuthService = Depends(_get_auth_service),
):
    try:
        access_token, new_refresh = await service.refresh(
            raw_refresh_token=body.refresh_token,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        return TokenResponse(access_token=access_token, refresh_token=new_refresh)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalidate current session tokens",
)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    service: AuthService = Depends(_get_auth_service),
):
    await service.logout(
        raw_access_token=credentials.credentials,
        user_id=current_user.id,
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserProfileResponse.model_validate(current_user)
