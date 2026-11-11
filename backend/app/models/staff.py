import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import StaffRole, StatusEnum


class Staff(BranchScoped, BaseModel):
    __tablename__ = "staff"
    __table_args__ = (CheckConstraint("slot_minutes BETWEEN 5 AND 480", name="slot_minutes_range"),)

    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[StaffRole] = mapped_column(enum_col(StaffRole, "role", 20))
    department: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200), unique=True)
    schedule: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[StatusEnum] = mapped_column(enum_col(StatusEnum, "status", 10), default=StatusEnum.active)
    # shifokorning standart qabul davomiyligi (xizmat turida davomiylik bo'lmasa)
    slot_minutes: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    joined_date: Mapped[date | None] = mapped_column(Date)


class User(BranchScoped, BaseModel):
    """Login hisobi. Bitta xodimda bitta login (staff_id unikal)."""

    __tablename__ = "users"

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), unique=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
