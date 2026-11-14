# ruff: noqa: E501
"""Login talab qilmaydigan ochiq endpointlar: imzolangan havola bilan qabulni tasdiqlash/bekor qilish va bo'sh vaqtni band qilish."""
import uuid
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Appointment, ClinicSettings, Patient, Staff, WaitlistEntry
from app.schemas.enums import AppointmentStatus, WaitlistStatus
from app.services import audit, links, offers
from app.services.booking import SystemActor, booking_conflicts, build_appointment
from app.services.periods import CLINIC_TZ

router = APIRouter()
TAG = "🌐 Public"


class AppointmentView(BaseModel):
    clinic: str
    date: str
    time: str
    doctor: str
    status: str
    confirmed: bool
    can_act: bool


class OfferView(BaseModel):
    clinic: str
    date: str
    time: str
    doctor: str
    available: bool


def _clinic(db: Session, branch_id: uuid.UUID) -> str:
    row = db.scalar(select(ClinicSettings).where(ClinicSettings.branch_id == branch_id))
    return row.clinic_name if row else "Klinika"


def _appt(db: Session, token: str, lock: bool = False) -> Appointment:
    data = links.read_token(token, "appt")
    if not data:
        raise HTTPException(410, "Havola yaroqsiz yoki muddati tugagan")
    stmt = select(Appointment).where(Appointment.id == uuid.UUID(data["id"]))
    appt = db.scalar(stmt.with_for_update() if lock else stmt)
    if not appt:
        raise HTTPException(404, "Qabul topilmadi")
    return appt


def _view(db: Session, appt: Appointment) -> dict:
    local = appt.starts_at.astimezone(CLINIC_TZ)
    active = appt.status == AppointmentStatus.scheduled and appt.starts_at > datetime.now(UTC)
    return {"clinic": _clinic(db, appt.branch_id), "date": local.strftime("%d.%m.%Y"), "time": local.strftime("%H:%M"),
            "doctor": db.get(Staff, appt.doctor_id).full_name, "status": appt.status.value, "confirmed": appt.confirmed_at is not None, "can_act": active}


@router.get("/public/appointments/{token}", tags=[TAG], response_model=AppointmentView, summary="Qabul (havola bo'yicha): minimal ma'lumot")
def public_appointment(token: str, db: Session = Depends(get_db)):
    return _view(db, _appt(db, token))


@router.post("/public/appointments/{token}/confirm", tags=[TAG], response_model=AppointmentView, summary="Qabulni tasdiqlash (login kerak emas)")
def public_confirm(token: str, request: Request, db: Session = Depends(get_db)):
    appt = _appt(db, token, lock=True)
    if appt.status != AppointmentStatus.scheduled or appt.starts_at <= datetime.now(UTC):
        raise HTTPException(409, "Qabul faol emas: tasdiqlab bo'lmaydi")
    if not appt.confirmed_at:
        appt.confirmed_at = datetime.now(UTC)
        audit.record(db, None, request, "update", "appointment", appt.id, {"confirmed": True, "via": "link", "patient_id": str(appt.patient_id)})
        db.commit()
    return _view(db, appt)


@router.post("/public/appointments/{token}/cancel", tags=[TAG], response_model=AppointmentView,
             summary="Qabulni bekor qilish (login kerak emas): vaqt bo'shaydi, kutish ro'yxatidagi bemorga taklif ketadi")
def public_cancel(token: str, request: Request, db: Session = Depends(get_db)):
    appt = _appt(db, token, lock=True)
    if appt.status != AppointmentStatus.scheduled or appt.starts_at <= datetime.now(UTC):
        raise HTTPException(409, "Qabul faol emas: bekor qilib bo'lmaydi")
    cancel_appointment(db, appt, "link", request)
    return _view(db, appt)


def cancel_appointment(db: Session, appt: Appointment, source: str, request: Request | None = None) -> None:
    """Qabulni bekor qiladi (bemor tomonidan), vaqt bo'shaydi va kutuvchiga taklif ketadi. Hammasi bir tranzaksiyada."""
    appt.status, appt.cancelled_at, appt.cancel_source = AppointmentStatus.cancelled, datetime.now(UTC), source
    audit.record(db, None, request, "update", "appointment", appt.id, {"status": "Cancelled", "via": source, "patient_id": str(appt.patient_id)})
    offers.offer_freed_slot(db, appt)
    db.commit()


def _offer(token: str) -> dict:
    data = links.read_token(token, "offer")
    if not data:
        raise HTTPException(410, "Havola yaroqsiz yoki muddati tugagan")
    return data


@router.get("/public/offers/{token}", tags=[TAG], response_model=OfferView, summary="Bo'shagan vaqt taklifi (havola bo'yicha)")
def public_offer(token: str, db: Session = Depends(get_db)):
    data = _offer(token)
    entry = db.get(WaitlistEntry, uuid.UUID(data["entry"]))
    starts = datetime.fromisoformat(data["starts"]).astimezone(CLINIC_TZ)
    doctor = db.get(Staff, uuid.UUID(data["doctor"]))
    return {"clinic": _clinic(db, entry.branch_id), "date": starts.strftime("%d.%m.%Y"), "time": starts.strftime("%H:%M"), "doctor": doctor.full_name,
            "available": entry.status == WaitlistStatus.waiting and starts > datetime.now(UTC)}


class BookedOut(BaseModel):
    date: str
    time: str
    doctor: str
    appointment_id: Optional[str] = None


@router.post("/public/offers/{token}/book", tags=[TAG], response_model=BookedOut, status_code=201,
             summary="Taklif qilingan vaqtni band qilish (login kerak emas)",
             description="Oddiy qabul qoidalari (ish vaqti, band vaqt) amal qiladi; kimdir ulgurgan bo'lsa 409. Kutish ro'yxati yozuvi `Booked` bo'ladi.")
def public_book_offer(token: str, request: Request, db: Session = Depends(get_db)):
    data = _offer(token)
    entry = db.scalar(select(WaitlistEntry).where(WaitlistEntry.id == uuid.UUID(data["entry"])).with_for_update())
    if not entry or entry.status != WaitlistStatus.waiting:
        raise HTTPException(409, "Taklif allaqachon ishlatilgan yoki bekor qilingan")
    starts = datetime.fromisoformat(data["starts"]).astimezone(CLINIC_TZ)
    if starts <= datetime.now(UTC):
        raise HTTPException(410, "Vaqt o'tib ketgan")
    patient, doctor = db.get(Patient, entry.patient_id), db.get(Staff, entry.doctor_id)
    room_id = uuid.UUID(data["room"]) if data.get("room") else None
    appt, violation = build_appointment(db, SystemActor(branch_id=entry.branch_id), patient, doctor, starts.date().isoformat(),
                                        starts.strftime("%H:%M"), entry.type, None, room_id, entry.notes, None)
    with booking_conflicts(db):
        db.flush()
        entry.appointment_id, entry.status = appt.id, WaitlistStatus.booked
        audit.record(db, None, request, "create", "appointment", appt.id, {"via": "offer", "patient_id": str(patient.id), "waitlist": str(entry.id)})
        db.commit()
    return {"date": starts.strftime("%d.%m.%Y"), "time": starts.strftime("%H:%M"), "doctor": doctor.full_name, "appointment_id": str(appt.id)}
