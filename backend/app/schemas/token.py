"""Token schemas."""

from typing import Literal

from pydantic import BaseModel


class Token(BaseModel):
    """OAuth2 token response with refresh token."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str | None = None
    exp: int | None = None
    type: Literal["access", "refresh"] | None = None


class RefreshTokenRequest(BaseModel):
    """Request body for token refresh.

    The refresh_token field is optional because the token may also
    be provided via an httpOnly cookie.
    """

    refresh_token: str | None = None
