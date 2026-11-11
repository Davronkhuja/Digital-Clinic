"""Shifokorning ish oynalari: haftalik shablon + istisnolar; bo'sh vaqtlar va qabul ish vaqtiga tushishini tekshirish."""
import uuid
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models import Appointment, DoctorSchedule, ScheduleException, Staff
from app.models.appointment import BUSY_STATUSES
from app.schemas.enums import ExceptionKind
from app.services.periods import CLINIC_TZ

Window = tuple[datetime, datetime]


def _at(day: date, t: time) -> datetime:
    return datetime.combine(day, t, tzinfo=CLINIC_TZ)


def _split(day: date, start: time, end: time, b_start: time | None, b_end: time | None) -> list[Window]:
    if b_start is not None and b_end is not None:
        return [(_at(day, start), _at(day, b_start)), (_at(day, b_end), _at(day, end))]
    return [(_at(day, start), _at(day, end))]


def day_windows(db: Session, staff_id: uuid.UUID, day: date) -> list[Window]:
    """Klinika kunidagi ish oynalari (tanaffus ayirilgan). Ustuvorlik: ExtraWork > ta'til/kasallik/dam olish > shablon.
    Shablon umuman belgilanmagan shifokor butun kun ishlaydi (cheklovsiz); istisnolar baribir amal qiladi."""
    exceptions = db.scalars(
        select(ScheduleException).where(
            ScheduleException.staff_id == staff_id, ScheduleException.date_from <= day, ScheduleException.date_to >= day
        )
    ).all()
    extra = [e for e in exceptions if e.kind == ExceptionKind.extra_work]
    if extra:
        return sorted(w for e in extra for w in _split(day, e.start_time, e.end_time, e.break_start, e.break_end))
    if exceptions:
        return []
    row = db.scalar(select(DoctorSchedule).where(DoctorSchedule.staff_id == staff_id, DoctorSchedule.weekday == day.weekday()))
    if row:
        return _split(day, row.start_time, row.end_time, row.break_start, row.break_end)
    if db.scalar(select(exists().where(DoctorSchedule.staff_id == staff_id))):
        return []  # shablon bor, bu kun unda yo'q: dam olish kuni
    return [(_at(day, time.min), _at(day, time.min) + timedelta(days=1))]


def ensure_working(db: Session, doctor: Staff, starts_at: datetime, ends_at: datetime) -> None:
    """Qabul to'liq bitta ish oynasi ichida bo'lishi shart, aks holda 422."""
    start, end = starts_at.astimezone(CLINIC_TZ), ends_at.astimezone(CLINIC_TZ)
    if any(w_start <= start and end <= w_end for w_start, w_end in day_windows(db, doctor.id, start.date())):
        return
    raise HTTPException(422, "Shifokor bu vaqtda ishlamaydi (ish soatlari, tanaffus, ta'til yoki dam olish kuni)")


def free_slots(db: Session, doctor: Staff, day: date, duration_min: int, step_min: int = 15,
               room_id: uuid.UUID | None = None, now: datetime | None = None) -> list[tuple[datetime, datetime]]:
    windows = day_windows(db, doctor.id, day)
    if not windows:
        return []
    lo, hi = windows[0][0], windows[-1][1]
    stmt = select(Appointment.starts_at, Appointment.ends_at).where(
        Appointment.status.in_(BUSY_STATUSES), Appointment.starts_at < hi, Appointment.ends_at > lo
    )
    if room_id:
        stmt = stmt.where((Appointment.doctor_id == doctor.id) | (Appointment.room_id == room_id))
    else:
        stmt = stmt.where(Appointment.doctor_id == doctor.id)
    busy = db.execute(stmt).all()
    length = timedelta(minutes=duration_min)
    out: list[tuple[datetime, datetime]] = []
    for w_start, w_end in windows:
        t = w_start
        while t + length <= w_end:
            if (now is None or t >= now) and not any(b_start < t + length and b_end > t for b_start, b_end in busy):
                out.append((t, t + length))
            t += timedelta(minutes=step_min)
    return out
