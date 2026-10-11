"""Authentication endpoints: register, login, logout, current user."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ConflictError
from app.core.security import (
    CurrentUser,
    UnauthorizedError,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_session
from app.models import User
from app.repositories import users as user_repo
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.audit import log_action

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(body: RegisterRequest, session: Session = Depends(get_session)) -> User:
    """Create an account. Role is always `user` — privileged roles can only be
    granted by an admin through a dedicated (future) admin endpoint."""
    if user_repo.get_by_email(session, body.email) is not None:
        raise ConflictError("An account with this email already exists.")
    user = user_repo.create(
        session,
        email=body.email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
    )
    log_action(session, actor=user, action="user.registered", target_type="user", target_id=user.id)
    session.commit()
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    user = user_repo.get_by_email(session, body.email)
    if user is None or not verify_password(body.password, user.password_hash or ""):
        # Audit failed attempts — user FK only when the account exists.
        log_action(
            session,
            actor=user,
            action="user.login_failed",
            target_type="user",
            target_id=user.id if user else None,
        )
        session.commit()
        raise UnauthorizedError("Invalid email or password.")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled.")
    token = create_access_token(user.id, settings)
    return TokenResponse(
        access_token=token, expires_in_minutes=settings.access_token_expire_minutes
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current: CurrentUser, session: Session = Depends(get_session)) -> None:
    """JWT is stateless — the client discards the token. This endpoint exists to
    record the sign-out event in the audit log."""
    log_action(
        session,
        actor=current,
        action="user.logout",
        target_type="user",
        target_id=current.id,
    )
    session.commit()


@router.get("/me", response_model=UserResponse)
def me(current: CurrentUser) -> User:
    return current
