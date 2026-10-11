"""User data access."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def get_by_email(session: Session, email: str) -> User | None:
    return session.execute(
        select(User).where(User.email == email.lower())
    ).scalar_one_or_none()


def get_by_id(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def create(
    session: Session, *, email: str, full_name: str, password_hash: str
) -> User:
    user = User(email=email.lower(), full_name=full_name, password_hash=password_hash)
    session.add(user)
    session.flush()
    return user
