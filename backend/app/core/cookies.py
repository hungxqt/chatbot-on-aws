"""Cookie utilities for httpOnly auth cookies."""

from fastapi import Response

from app.core.config import settings


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set httpOnly auth cookies on response."""
    response.set_cookie(
        key=settings.ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path=settings.COOKIE_PATH,
    )
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/api/v1/auth",
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies."""
    response.delete_cookie(
        key=settings.ACCESS_TOKEN_COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path=settings.COOKIE_PATH,
    )
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path="/api/v1/auth",
    )
