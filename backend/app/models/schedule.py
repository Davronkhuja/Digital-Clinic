import uuid
from datetime import date, time

from sqlalchemy import CheckConstraint, Date, ForeignKey, SmallInteger, String, Time, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import ExceptionKind


class DoctorSchedule(BranchScoped, BaseModel):
    """Shifokorning haftalik shabloni: hafta kuni (0=dushanba) bo'yicha ish soatlari va tanaffus.

    Vaqtlar klinika (Asia/Tashkent) devor soati: takrorlanuvchi shablon, aniq lahza emas.
    Qabullarning o'zi timestamptz da saqlanadi. Shablon filial bo'yicha: shifokor bir nechta filialda ishlasa har filialda alohida
    shablon; bir hafta kunida ikki filial oynalari kesishmaydi (bazadagi exclusion cheklov).
    """

    __tablename__ = "doctor_schedules"
    __table_args__ = (
        UniqueConstraint("staff_id", "branch_id", "weekday"),
        ExcludeConstraint(("staff_id", "="), ("weekday", "="), ("branch_id", "<>"),
                          (func.tsrange(text("timestamp '2000-01-01' + start_time"), text("timestamp '2000-01-01' + end_time")), "&&"),
                          using="gist", name="no_cross_branch_schedule"),
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


class ScheduleException(BranchScoped, BaseModel):
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
        ExcludeConstraint(("staff_id", "="), ("branch_id", "<>"),
                          (func.tsrange(text("date_from + start_time"), text("date_from + end_time")), "&&"),
                          using="gist", where=text("kind = 'ExtraWork'"), name="no_cross_branch_extra_work"),
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


class StaffBranch(BaseModel):
    """Xodim ishlaydigan filiallar (shifokor bir nechta filialda ishlay oladi). Asosiy filial (`staff.branch_id`) doim kiradi."""

    __tablename__ = "staff_branches"
    __table_args__ = (UniqueConstraint("staff_id", "branch_id"),)

    staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), index=True)


def _link_home_branch(mapper, connection, staff) -> None:
    """Yangi xodim asosiy filialida ishlaydi (`staff_branches` ga avtomatik)."""
    from sqlalchemy import insert
    connection.execute(insert(StaffBranch.__table__).values(staff_id=staff.id, branch_id=staff.branch_id))


from sqlalchemy import event  # noqa: E402

from app.models.staff import Staff  # noqa: E402

event.listen(Staff, "after_insert", _link_home_branch)
