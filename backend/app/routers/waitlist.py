import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Patient, Staff, WaitlistEntry
from app.schemas import Appointment as AppointmentOut
from app.schemas.appointments import WaitlistBook, WaitlistCreate, WaitlistOut, WaitlistSuggestion, WaitlistUpdate
from app.schemas.enums import WaitlistStatus
from app.services import availability, queries
from app.services.booking import build_appointment, resolve_room, save_booking
from app.services.lookup import get_patient_or_404, resolve_doctor
from app.services.periods import CLINIC_TZ, clinic_today
from app.services.scheduling import resolve_duration

router = APIRouter()
TAG = "⏳ Waitlist"
SUGGEST_HORIZON_DAYS = 30


def _out(e: WaitlistEntry, patient: Patient, doctor: Staff) -> dict:
    return {
        "id": str(e.id), "patient_id": str(e.patient_id), "patient_name": patient.full_name, "patient_phone": patient.phone,
        "doctor_id": str(e.doctor_id), "doctor": doctor.full_name, "type": e.type, "date_from": e.date_from.isoformat(),
        "date_to": e.date_to.isoformat() if e.date_to else None, "status": e.status,
        "appointment_id": str(e.appointment_id) if e.appointment_id else None, "notes": e.notes,
        "created_at": e.created_at.astimezone(CLINIC_TZ).date().isoformat(),
    }


def _load(db: Session, entry_id: uuid.UUID) -> tuple[WaitlistEntry, Patient, Staff]:
    row = db.execute(
        select(WaitlistEntry, Patient, Staff).join(Patient, WaitlistEntry.patient_id == Patient.id)
        .join(Staff, WaitlistEntry.doctor_id == Staff.id).where(WaitlistEntry.id == entry_id)
    ).first()
    if not row:
        raise HTTPException(404, "Kutish ro'yxati yozuvi topilmadi")
    return row


def _parse(value: str | None, field: str) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        raise HTTPException(422, f"{field} noto'g'ri sana")


@router.get("/waitlist", tags=[TAG], response_model=List[WaitlistOut], summary="Kutish ro'yxati",
            description="Eng eski birinchi (FIFO). `for_date`: shu sanani xohlagan (oralig'iga tushadigan) kutuvchilar, "
                        "masalan bekor qilingan qabul o'rniga.")
def get_waitlist(
    status: Optional[WaitlistStatus] = Query(WaitlistStatus.waiting),
    doctor_id: Optional[uuid.UUID] = None,
    for_date: Optional[date] = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require("appointments:read")),
):
    stmt = (select(WaitlistEntry, Patient, Staff).join(Patient, WaitlistEntry.patient_id == Patient.id)
            .join(Staff, WaitlistEntry.doctor_id == Staff.id).order_by(WaitlistEntry.created_at, WaitlistEntry.id))
    stmt = stmt.where(WaitlistEntry.branch_id == user.branch_id)
    if status:
        stmt = stmt.where(WaitlistEntry.status == status)
    if doctor_id:
        stmt = stmt.where(WaitlistEntry.doctor_id == doctor_id)
    if for_date:
        stmt = stmt.where(WaitlistEntry.date_from <= for_date,
                          (WaitlistEntry.date_to.is_(None)) | (WaitlistEntry.date_to >= for_date))
    return [_out(*row) for row in db.execute(stmt).all()]


@router.post("/waitlist", tags=[TAG], response_model=WaitlistOut, status_code=201, summary="Kutish ro'yxatiga qo'shish")
def add_to_waitlist(data: WaitlistCreate, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require("appointments:write"))):
    patient = get_patient_or_404(db, data.patient_id)
    doctor = resolve_doctor(db, data.doctor_id, data.doctor)
    date_from, date_to = _parse(data.date_from, "date_from") or clinic_today(), _parse(data.date_to, "date_to")
    if date_to and date_to < date_from:
        raise HTTPException(422, "date_to date_from dan oldin bo'lishi mumkin emas")
    entry = WaitlistEntry(patient_id=patient.id, doctor_id=doctor.id, type=data.type, date_from=date_from,
                          date_to=date_to, notes=data.notes, branch_id=user.branch_id, created_by=user.id)
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bemor bu shifokorni allaqachon kutmoqda")
    return _out(entry, patient, doctor)


@router.patch("/waitlist/{entry_id}", tags=[TAG], response_model=WaitlistOut, summary="Oraliq/izohni o'zgartirish yoki bekor qilish")
def update_waitlist(entry_id: uuid.UUID, data: WaitlistUpdate, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require("appointments:write"))):
    entry, patient, doctor = _load(db, entry_id)
    if entry.status != WaitlistStatus.waiting:
        raise HTTPException(409, "Faqat kutilayotgan yozuvni o'zgartirish mumkin")
    fields = data.model_dump(exclude_unset=True)
    if fields.get("date_from"):
        entry.date_from = _parse(fields["date_from"], "date_from")
    if "date_to" in fields:
        entry.date_to = _parse(fields["date_to"], "date_to")
    if entry.date_to and entry.date_to < entry.date_from:
        raise HTTPException(422, "date_to date_from dan oldin bo'lishi mumkin emas")
    if "notes" in fields:
        entry.notes = fields["notes"]
    if fields.get("status") == "Cancelled":
        entry.status = WaitlistStatus.cancelled
    db.commit()
    return _out(entry, patient, doctor)


@router.get("/waitlist/{entry_id}/suggestions", tags=[TAG], response_model=List[WaitlistSuggestion],
            summary="Kutuvchi uchun eng yaqin bo'sh vaqtlar",
            description="Xohlagan oraliqda (oraliq cheklanmagan bo'lsa 30 kun) shifokorning bo'sh vaqtlari, kuniga 3 tadan.")
def waitlist_suggestions(entry_id: uuid.UUID, limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db),
                         user: CurrentUser = Depends(require("appointments:read"))):
    entry, _patient, doctor = _load(db, entry_id)
    if entry.status != WaitlistStatus.waiting:
        raise HTTPException(409, "Faqat kutilayotgan yozuv uchun")
    first = max(entry.date_from, clinic_today())
    last = entry.date_to or first + timedelta(days=SUGGEST_HORIZON_DAYS)
    duration = resolve_duration(db, doctor, entry.type)
    room = resolve_room(db, None, doctor)
    now = datetime.now(CLINIC_TZ)
    out: list[dict] = []
    day = first
    while day <= last and len(out) < limit:
        for start, end in availability.free_slots(db, doctor, day, duration, 15, room.id if room else None, now)[:3]:
            out.append({"date": day.isoformat(), "time": start.astimezone(CLINIC_TZ).strftime("%H:%M"),
                        "end_time": end.astimezone(CLINIC_TZ).strftime("%H:%M")})
        day += timedelta(days=1)
    return out[:limit]


@router.post("/waitlist/{entry_id}/book", tags=[TAG], response_model=AppointmentOut, status_code=201,
             summary="Kutuvchini qabulga yozish",
             description="Oddiy qabul qoidalari (ish vaqti, band vaqt) amal qiladi; muvaffaqiyatda yozuv `Booked` bo'ladi, "
                         "bitta tranzaksiyada.")
def book_from_waitlist(entry_id: uuid.UUID, data: WaitlistBook, request: Request, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require("appointments:write"))):
    entry, patient, doctor = _load(db, entry_id)
    if entry.status != WaitlistStatus.waiting:
        raise HTTPException(409, "Faqat kutilayotgan yozuvni band qilish mumkin")
    appt, violation = build_appointment(db, user, patient, doctor, data.date, data.time, entry.type, data.duration_min,
                                        data.room_id, entry.notes, data.override_reason)

    def mark_booked() -> None:
        entry.appointment_id = appt.id
        entry.status = WaitlistStatus.booked

    save_booking(db, user, request, appt, violation, mark_booked)
    return queries.list_appointments(db, appt_id=appt.id)[0]
