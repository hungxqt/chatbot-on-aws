"""Authentication routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionSvc, UserSvc
from app.core.config import settings
from app.core.cookies import clear_auth_cookies, set_auth_cookies
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, create_refresh_token
from app.schemas.token import RefreshTokenRequest, Token
from app.schemas.user import UserCreate, UserRead

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_service: UserSvc,
    session_service: SessionSvc,
) -> Any:
    """OAuth2 compatible token login.

    Returns access token and refresh token in JSON body.
    Also sets httpOnly cookies for browser-based authentication.
    """
    user = await user_service.authenticate(form_data.username, form_data.password)
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    await session_service.create_session(
        user_id=user.id,
        refresh_token=refresh_token,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )

    response = JSONResponse(
        content={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    )
    set_auth_cookies(response, access_token, refresh_token)
    return response


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    user_service: UserSvc,
) -> Any:
    """Register a new user."""
    user = await user_service.register(user_in)
    return user


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    body: RefreshTokenRequest,
    user_service: UserSvc,
    session_service: SessionSvc,
) -> Any:
    """Get new access token using refresh token.

    Reads refresh token from cookie first, then falls back to request body.
    """
    token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not token:
        token = body.refresh_token

    if not token:
        raise AuthenticationError(message="Refresh token not provided")

    session = await session_service.validate_refresh_token(token)
    if not session:
        raise AuthenticationError(message="Invalid or expired refresh token")

    user = await user_service.get_by_id(session.user_id)
    if not user.is_active:
        raise AuthenticationError(message="User account is disabled")

    access_token = create_access_token(subject=str(user.id))
    new_refresh_token = create_refresh_token(subject=str(user.id))

    await session_service.logout_by_refresh_token(token)
    await session_service.create_session(
        user_id=user.id,
        refresh_token=new_refresh_token,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )

    response = JSONResponse(
        content={
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }
    )
    set_auth_cookies(response, access_token, new_refresh_token)
    return response


@router.post("/logout", status_code=status.HTTP_200_OK, response_model=None)
async def logout(
    request: Request,
    session_service: SessionSvc,
) -> Any:
    """Logout and invalidate the current session.

    Reads refresh token from cookie or request body, clears auth cookies.
    """
    token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)

    if not token:
        try:
            body = await request.json()
            token = body.get("refresh_token")
        except Exception:
            pass

    if token:
        await session_service.logout_by_refresh_token(token)

    response = JSONResponse(content={"message": "Logged out"}, status_code=200)
    clear_auth_cookies(response)
    return response


@router.get("/me", response_model=UserRead)
async def get_current_user_info(current_user: CurrentUser) -> Any:
    """Get current authenticated user information."""
    return current_user
