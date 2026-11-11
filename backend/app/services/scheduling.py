"""Qabul vaqti va davomiyligi: klinika vaqti (Asia/Tashkent) <-> timestamptz, davomiylikni aniqlash."""
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AppointmentType, Staff
from app.models.appointment import clinic_datetime

DEFAULT_SLOT_MIN = 30


def type_duration(db: Session, type_name: str) -> int | None:
    return db.scalar(
        select(AppointmentType.duration_min).where(
            func.lower(AppointmentType.name) == type_name.strip().lower(), AppointmentType.is_active.is_(True)
        )
    )


def resolve_duration(db: Session, doctor: Staff, type_name: str, override: int | None = None) -> int:
    """Ustuvorlik: so'rovdagi qiymat -> xizmat turi davomiyligi -> shifokor standarti -> 30 daqiqa."""
    return override or type_duration(db, type_name) or doctor.slot_minutes or DEFAULT_SLOT_MIN


def appointment_window(day: str, at: str, duration_min: int) -> tuple[datetime, datetime]:
    """'2026-12-01', '10:00' (klinika vaqti) -> (starts_at, ends_at) UTC. ValueError noto'g'ri sana/vaqtda."""
    starts = clinic_datetime(date.fromisoformat(day), time.fromisoformat(at))
    return starts, starts + timedelta(minutes=duration_min)
