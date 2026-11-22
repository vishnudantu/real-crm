"""Authentication HTTP endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    ResetPasswordRequest,
    ResetPasswordConfirmRequest,
    ResetPasswordResponse,
    RevokeAllResponse,
    TokenResponse,
)
from app.modules.auth.service import (
    change_password,
    cleanup_expired_revocations,
    login_user,
    refresh_access_token,
    request_password_reset,
    confirm_password_reset,
    revoke_access_token,
    register_buyer,
    revoke_all_user_refresh_tokens,
)
from app.modules.users.models import User
from app.modules.auth.security import decode_access_token
from app.modules.users.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a buyer account",
)
def register(
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Create a public buyer account.

    Role selection is intentionally absent from the request schema; every
    public registration receives the BUYER role.
    """

    return register_buyer(
        db,
        full_name=payload.full_name,
        email=str(payload.email),
        password=payload.password.get_secret_value(),
        phone=payload.phone,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive an access token and refresh token",
)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Authenticate credentials and issue a short-lived access token plus a
    long-lived refresh token."""

    result = login_user(
        db,
        email=str(payload.email),
        password=payload.password.get_secret_value(),
        settings=settings,
    )
    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        refresh_token=result.refresh_token,
        refresh_expires_in=result.refresh_expires_in,
    )


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Request a single-use password-reset token",
)
def reset_password_endpoint(
    payload: ResetPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResetPasswordResponse:
    """Request a password-reset token without revealing account existence."""

    from app.modules.auth.email import deliver_password_reset

    token = request_password_reset(
        db, email=str(payload.email), settings=settings
    )
    if token is not None:
        deliver_password_reset(
            settings=settings,
            recipient_email=str(payload.email),
            token=token,
            frontend_base_url=request.base_url,
        )
    return ResetPasswordResponse(
        message=(
            "If an account exists for this email, password-reset instructions "
            "have been sent."
        )
    )


@router.post(
    "/reset-password/confirm",
    response_model=ResetPasswordResponse,
    summary="Complete a password reset with a single-use token",
)
def reset_password_confirm_endpoint(
    payload: ResetPasswordConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResetPasswordResponse:
    return confirm_password_reset(
        db,
        token=payload.token,
        new_password=payload.password.get_secret_value(),
        settings=settings,
    )


@router.post(
    "/change-password",
    response_model=LogoutResponse,
    summary="Change the authenticated user's password",
)
def change_password_endpoint(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> LogoutResponse:
    """Verify the current password and invalidate all existing sessions."""

    return change_password(
        db,
        user=current_user,
        current_password=payload.current_password.get_secret_value(),
        new_password=payload.new_password.get_secret_value(),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the current user's profile",
)
def me(current_user: CurrentUser) -> User:
    """Return the authenticated user's safe profile fields."""

    return current_user


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    summary="Exchange a refresh token for a new access token",
)
def refresh(
    payload: RefreshTokenRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RefreshTokenResponse:
    """Rotate a refresh token into a new short-lived access token."""

    return refresh_access_token(
        db,
        refresh_token=payload.refresh_token,
        settings=settings,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Revoke the current session server-side",
)
def logout(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> LogoutResponse:
    """Revoke the current access token and every refresh session."""

    claims = request.state.token_claims
    revoke_access_token(
        db,
        jti=claims.jti,
        user_id=current_user.id,
        expires_at=datetime.fromtimestamp(claims.expires_at, UTC),
        tenant_id=current_user.tenant_id,
    )
    revoke_all_user_refresh_tokens(db, user_id=current_user.id)
    cleanup_expired_revocations(db)
    return LogoutResponse(message="Logged out successfully.")


@router.post(
    "/revoke-all",
    response_model=RevokeAllResponse,
    summary="Revoke all refresh tokens for the current user",
)
def revoke_all(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> RevokeAllResponse:
    """Revoke every refresh token and access token for the current user."""

    current_user.security_version += 1
    db.add(current_user)
    revoke_all_user_refresh_tokens(db, user_id=current_user.id)
    cleanup_expired_revocations(db)
    return RevokeAllResponse(message="All sessions revoked.")
