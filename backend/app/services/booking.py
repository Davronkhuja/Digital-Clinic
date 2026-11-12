"""Qabul yozish: kabinetni aniqlash va band vaqt cheklovini (bazadagi exclusion) 409 ga aylantirish."""
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.models import Appointment, Patient, Room, Staff
from app.services import audit, availability
from app.services.scheduling import appointment_window, resolve_duration

BUSY_MESSAGES = {
    "no_doctor_overlap": "Shifokor bu vaqtda band: boshqa qabul bilan kesishadi",
    "no_room_overlap": "Kabinet bu vaqtda band: boshqa qabul bilan kesishadi",
}


def resolve_room(db: Session, room_id: uuid.UUID | None, doctor: Staff) -> Room | None:
    """Aniq ko'rsatilgan kabinet (faol, shifokor filialida bo'lishi shart), bo'lmasa shifokorning standart kabineti."""
    if room_id:
        room = db.get(Room, room_id)
        if not room or not room.is_active:
            raise HTTPException(422, "Kabinet topilmadi yoki faol emas")
        if room.branch_id != doctor.branch_id:
            raise HTTPException(422, "Kabinet shifokor filialiga tegishli emas")
        return room
    if doctor.default_room_id:
        room = db.get(Room, doctor.default_room_id)
        return room if room and room.is_active else None
    return None


@contextmanager
def booking_conflicts(db: Session) -> Iterator[None]:
    """Band vaqt (bazadagi exclusion cheklov) bo'lsa 409; poyga holatida ham ishlaydi (flush/commit paytida)."""
    try:
        yield
    except IntegrityError as exc:
        db.rollback()
        name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if name in BUSY_MESSAGES:
            raise HTTPException(409, BUSY_MESSAGES[name])
        raise


def commit_booking(db: Session) -> None:
    with booking_conflicts(db):
        db.commit()


OVERRIDE_PERM = "appointments:override"
MIN_REASON = 5


def apply_working_rule(db: Session, user: CurrentUser, doctor: Staff, appt: Appointment, override_reason: str | None) -> str | None:
    """Ish vaqti qoidasi. Buzilsa: sabab bilan va `appointments:override` ruxsati bilan majburan yoziladi (qaytaradi buzilish
    matnini, audit uchun), aks holda 422/403. Buzilmasa eski override izi tozalanadi. Band vaqt (shifokor/kabinet) bu yerda
    emas: u baribir bazada taqiqlangan."""
    violation = availability.working_violation(db, doctor, appt.starts_at, appt.ends_at)
    if not violation:
        appt.override_reason = appt.override_by = None
        return None
    reason = (override_reason or "").strip()
    if not reason:
        raise HTTPException(422, violation)
    if OVERRIDE_PERM not in user.permissions:
        raise HTTPException(403, f"Ish vaqtidan tashqari yozish uchun ruxsat yo'q ({OVERRIDE_PERM})")
    if len(reason) < MIN_REASON:
        raise HTTPException(422, f"Majburan yozish sababi majburiy (kamida {MIN_REASON} belgi)")
    appt.override_reason, appt.override_by = reason[:500], user.id
    return violation


def save_booking(db: Session, user: CurrentUser, request: Request, appt: Appointment, violation: str | None,
                 *extra_updates) -> None:
    """flush + (override bo'lsa) audit + commit, band vaqt bo'lsa 409. Override auditga alohida `override` hodisasi bilan yoziladi."""
    with booking_conflicts(db):
        db.flush()
        for update in extra_updates:
            update()
        if violation:
            audit.record(db, user, request, "override", "appointment", appt.id,
                         {"reason": appt.override_reason, "violation": violation, "doctor_id": str(appt.doctor_id),
                          "patient_id": str(appt.patient_id), "starts_at": appt.starts_at.isoformat()})
        db.commit()


def build_appointment(db: Session, user: CurrentUser, patient: Patient, doctor: Staff, day: str, at: str, type_name: str,
                      duration_min: int | None = None, room_id: uuid.UUID | None = None,
                      notes: str | None = None, override_reason: str | None = None) -> tuple[Appointment, str | None]:
    """Qabul qoidalari: davomiylik, ish oynasi (sabab bilan majburan yozish mumkin), kabinet. Sessiyaga qo'shadi;
    (qabul, override buzilishi) qaytaradi, saqlash `save_booking` bilan."""
    duration = resolve_duration(db, doctor, type_name, duration_min)
    try:
        starts_at, ends_at = appointment_window(day, at, duration)
    except ValueError:
        raise HTTPException(422, "Sana yoki vaqt noto'g'ri")
    room = resolve_room(db, room_id, doctor)
    appt = Appointment(
        patient_id=patient.id, doctor_id=doctor.id, room_id=room.id if room else None, starts_at=starts_at,
        ends_at=ends_at, type=type_name, notes=notes, branch_id=user.branch_id, created_by=user.id,
    )
    violation = apply_working_rule(db, user, doctor, appt, override_reason)
    db.add(appt)
    return appt, violation
