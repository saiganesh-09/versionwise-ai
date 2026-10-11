"""Password hashing, JWT issue/verify, and FastAPI auth dependencies.

Token transport: `Authorization: Bearer <jwt>`. Trade-off vs httpOnly cookies:
no CSRF surface and trivially testable; downside is XSS exposure of whatever
store holds the token on the client — mitigated by React escaping + short
expiry. Documented in docs/ARCHITECTURE.md.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_session
from app.models import User, UserRole

ALGORITHM = "HS256"
TOKEN_TYPE = "access"

_password_hash = PasswordHash.recommended()  # argon2id

_bearer = HTTPBearer(auto_error=False)


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"

    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__(message)


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"

    def __init__(self, message: str = "Insufficient permissions.") -> None:
        super().__init__(message)


def hash_password(plain: str) -> str:
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _password_hash.verify(plain, hashed)
    except Exception:
        return False


def create_access_token(user_id: uuid.UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    """Return the user id claim or raise UnauthorizedError."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != TOKEN_TYPE:
            raise UnauthorizedError("Invalid token type.")
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise UnauthorizedError("Invalid or expired token.") from exc


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Resolve the bearer token to a live, active user row.

    Role claims are never read from the token — the DB row is authoritative.
    """
    if creds is None:
        raise UnauthorizedError()
    user_id = decode_access_token(creds.credentials, settings)
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Account not found or inactive.")
    return user


def require_roles(*roles: UserRole):
    """Dependency factory: current user must hold one of the given roles."""

    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise ForbiddenError()
        return user

    return checker


CurrentUser = Annotated[User, Depends(get_current_user)]
