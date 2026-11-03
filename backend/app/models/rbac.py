import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BaseModel

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(BaseModel):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(60), unique=True)  # masalan: patients:read
    description: Mapped[str | None] = mapped_column(String(200))


class Role(BaseModel):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(30), unique=True)  # admin, doctor, nurse, receptionist, cashier
    name: Mapped[str] = mapped_column(String(80))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    permissions: Mapped[list[Permission]] = relationship(secondary=role_permissions, lazy="selectin")


__all__ = ["Permission", "Role", "role_permissions", "uuid"]
