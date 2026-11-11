import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    cast,
    func,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import AppointmentStatus
from app.services.periods import CLINIC_TZ

CLINIC_TZ_NAME = "Asia/Tashkent"


class AppointmentType(BaseModel):
    """Qabul turi va uning standart davomiyligi (daqiqa). Uchrashuvning `type` maydoni shu nomga mos keladi."""

    __tablename__ = "appointment_types"
    __table_args__ = (
        CheckConstraint("duration_min BETWEEN 5 AND 480", name="duration_range"),
        Index("uq_appointment_types_name_lower", func.lower(text("name")), unique=True),
    )

    name: Mapped[str] = mapped_column(String(60))
    duration_min: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Appointment(BranchScoped, BaseModel):
    __tablename__ = "appointments"
    __table_args__ = (CheckConstraint("ends_at > starts_at", name="ends_after_start"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="RESTRICT"), index=True
    )
    # Vaqt timestamptz da (UTC); klinika vaqti (Asia/Tashkent) faqat ko'rsatishda
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    type: Mapped[str] = mapped_column(String(60))
    status: Mapped[AppointmentStatus] = mapped_column(
        enum_col(AppointmentStatus, "status", 12), default=AppointmentStatus.scheduled
    )
    notes: Mapped[str | None] = mapped_column(Text)

    @hybrid_property
    def date(self) -> date:  # klinika vaqti bo'yicha sana
        return self.starts_at.astimezone(CLINIC_TZ).date()

    @date.inplace.expression
    @classmethod
    def _date_expr(cls):
        return cast(func.timezone(literal_column(f"'{CLINIC_TZ_NAME}'"), cls.starts_at), Date)

    @hybrid_property
    def time(self) -> time:  # klinika vaqti bo'yicha soat
        return self.starts_at.astimezone(CLINIC_TZ).time()

    @time.inplace.expression
    @classmethod
    def _time_expr(cls):
        return cast(func.timezone(literal_column(f"'{CLINIC_TZ_NAME}'"), cls.starts_at), Time)

    @property
    def duration_min(self) -> int:
        return int((self.ends_at - self.starts_at).total_seconds() // 60)


def clinic_datetime(day: date, at: time) -> datetime:
    """Klinika vaqtidagi sana+soat -> UTC timestamptz."""
    return datetime.combine(day, at, tzinfo=CLINIC_TZ).astimezone(UTC)
