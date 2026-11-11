import uuid
from datetime import date, time

from sqlalchemy import CheckConstraint, Date, ForeignKey, SmallInteger, String, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, enum_col
from app.schemas.enums import ExceptionKind


class DoctorSchedule(BaseModel):
    """Shifokorning haftalik shabloni: hafta kuni (0=dushanba) bo'yicha ish soatlari va tanaffus.

    Vaqtlar klinika (Asia/Tashkent) devor soati: takrorlanuvchi shablon, aniq lahza emas.
    Qabullarning o'zi timestamptz da saqlanadi.
    """

    __tablename__ = "doctor_schedules"
    __table_args__ = (
        UniqueConstraint("staff_id", "weekday"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint("end_time > start_time", name="hours_order"),
        CheckConstraint(
            "(break_start IS NULL AND break_end IS NULL) OR "
            "(break_start IS NOT NULL AND break_end IS NOT NULL AND break_start < break_end "
            "AND break_start >= start_time AND break_end <= end_time)",
            name="break_valid",
        ),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    break_start: Mapped[time | None] = mapped_column(Time)
    break_end: Mapped[time | None] = mapped_column(Time)


class ScheduleException(BaseModel):
    """Istisno: ta'til/kasallik/dam olish (shu sanalarda ishlamaydi) yoki qo'shimcha ish kuni (shu soatlarda ishlaydi).

    ExtraWork shablondan ustun turadi; boshqalari shablonni bekor qiladi.
    """

    __tablename__ = "schedule_exceptions"
    __table_args__ = (
        CheckConstraint("date_to >= date_from", name="dates_order"),
        CheckConstraint(
            "(kind = 'ExtraWork' AND start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time "
            "AND date_from = date_to) OR (kind <> 'ExtraWork' AND start_time IS NULL AND end_time IS NULL)",
            name="kind_hours",
        ),
        CheckConstraint(
            "(break_start IS NULL AND break_end IS NULL) OR "
            "(kind = 'ExtraWork' AND break_start IS NOT NULL AND break_end IS NOT NULL AND break_start < break_end "
            "AND break_start >= start_time AND break_end <= end_time)",
            name="break_valid",
        ),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), index=True)
    kind: Mapped[ExceptionKind] = mapped_column(enum_col(ExceptionKind, "kind", 12))
    date_from: Mapped[date] = mapped_column(Date, index=True)
    date_to: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    break_start: Mapped[time | None] = mapped_column(Time)
    break_end: Mapped[time | None] = mapped_column(Time)
    note: Mapped[str | None] = mapped_column(String(200))
