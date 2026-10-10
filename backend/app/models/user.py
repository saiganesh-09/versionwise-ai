"""User account model. Auth flows arrive in Phase 3; the table exists now so
ownership/permission FKs can reference it."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.document import Document, DocumentPermissionGrant


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.user, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    documents: Mapped[list["Document"]] = relationship(back_populates="owner")
    permissions: Mapped[list["DocumentPermissionGrant"]] = relationship(
        back_populates="user", foreign_keys="DocumentPermissionGrant.user_id"
    )
