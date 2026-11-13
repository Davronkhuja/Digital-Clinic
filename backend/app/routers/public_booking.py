# ruff: noqa: E501
"""Onlayn yozilish: xizmat (qabul turi) -> shifokor -> bo'sh vaqt -> telefon (OTP). Login kerak emas; tezlik cheklovi, honeypot,
telefon OTP bilan tasdiqlanadi. Yangi bemor "onlayn" manbasi bilan yaratiladi; mavjud bemor (telefon + ism) qayta ishlatiladi (dublikat yaratilmaydi)."""
from datetime import UTC, date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.names import normalize_name
from app.db.session import get_db
from app.models import Appointment, AppointmentType, Branch, ClinicSettings, Patient, Staff
from app.routers.messaging import set_consent
from app.schemas.enums import AppointmentStatus, Channel, GenderEnum, StaffRole, StatusEnum
from app.services import audit, availability, links, messaging, otp
from app.services.booking import SystemActor, booking_conflicts, build_appointment
from app.services.periods import CLINIC_TZ, clinic_today
from app.services.phone import normalize_phone
from app.services.scheduling import resolve_duration

router = APIRouter()
TAG = "🌐 Online booking"
MAX_DAYS_AHEAD = 60
MAX_ACTIVE_PER_PHONE = 3


class OtpRequest(BaseModel):
    phone: str = Field(..., examples=["+998 90 123 45 67"])
    purpose: str = Field("booking", pattern="^(booking|portal|telegram)$")
    language: str = Field("uz", pattern="^(uz|ru)$")
    website: str = Field("", description="Honeypot: bo'sh bo'lishi kerak (botlar to'ldiradi)")


class OtpVerify(BaseModel):
    phone: str
    purpose: str = Field("booking", pattern="^(booking|portal|telegram)$")
    code: str = Field(..., min_length=4, max_length=8)


class BookingIn(BaseModel):
    token: str = Field(..., description="OTP tasdiqlangandan keyin berilgan token")
    name: str = Field(..., min_length=2, max_length=200)
    birth_date: Optional[date] = None
    doctor_id: str
    type: str
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    language: str = Field("uz", pattern="^(uz|ru)$")
    consent_sms: bool = Field(False, description="SMS eslatmalarga rozilik (voz kechish mumkin)")
    website: str = ""


def _branch(db: Session) -> Branch:
    return db.scalar(select(Branch).where(Branch.is_default.is_(True))) or db.scalar(select(Branch))


def _honeypot(value: str) -> None:
    if value.strip():
        raise HTTPException(422, "So'rov rad etildi")


@router.post("/public/otp/request", tags=[TAG], summary="Telefonga tasdiqlash kodi yuborish",
             description="6 raqamli kod SMS bilan (5 daqiqa, 5 urinish). Telefon uchun 15 daqiqada 3 ta, IP uchun soatiga 10 ta so'rov (429). Kod javobda qaytmaydi.")
def otp_request(data: OtpRequest, request: Request, db: Session = Depends(get_db)):
    _honeypot(data.website)
    phone = normalize_phone(data.phone)
    if not phone:
        raise HTTPException(422, "Telefon raqami noto'g'ri (+998 XX XXX XX XX)")
    otp.send_code(db, otp.request_ip(request), phone, data.purpose, _branch(db).id, data.language)
    return {"sent": True, "expires_in": int(otp.CODE_TTL.total_seconds())}


@router.post("/public/otp/verify", tags=[TAG], summary="Kodni tasdiqlash")
def otp_verify(data: OtpVerify, request: Request, db: Session = Depends(get_db)):
    phone = normalize_phone(data.phone)
    if not phone:
        raise HTTPException(422, "Telefon raqami noto'g'ri")
    otp.rate_check(db, otp.request_ip(request), "otp_verify_ip", 30, timedelta(hours=1))
    db.commit()
    return {"token": otp.verify_code(db, phone, data.purpose, data.code)}


@router.get("/public/booking/types", tags=[TAG], summary="Xizmatlar (qabul turlari) va davomiyligi")
def booking_types(db: Session = Depends(get_db)):
    return [{"name": t.name, "duration_min": t.duration_min} for t in db.scalars(select(AppointmentType).where(AppointmentType.is_active.is_(True)).order_by(AppointmentType.name))]


@router.get("/public/booking/doctors", tags=[TAG], summary="Faol shifokorlar")
def booking_doctors(db: Session = Depends(get_db)):
    rows = db.scalars(select(Staff).where(Staff.role == StaffRole.doctor, Staff.status == StatusEnum.active).order_by(Staff.full_name))
    return [{"id": str(d.id), "name": d.full_name, "department": d.department} for d in rows]


def _doctor(db: Session, doctor_id: str) -> Staff:
    try:
        import uuid

        doctor = db.get(Staff, uuid.UUID(doctor_id))
    except ValueError:
        doctor = None
    if not doctor or doctor.role != StaffRole.doctor or doctor.status != StatusEnum.active:
        raise HTTPException(404, "Shifokor topilmadi")
    return doctor


def _check_date(day: date) -> None:
    today = clinic_today()
    if day < today or day > today + timedelta(days=MAX_DAYS_AHEAD):
        raise HTTPException(422, f"Sana bugundan {MAX_DAYS_AHEAD} kungacha bo'lishi kerak")


@router.get("/public/booking/slots", tags=[TAG], summary="Bo'sh vaqtlar (shifokor, sana, xizmat)")
def booking_slots(doctor_id: str, date: date, type: str = Query(...), request: Request = None, db: Session = Depends(get_db)):
    otp.rate_check(db, otp.request_ip(request), "slots_ip", 120, timedelta(hours=1))
    db.commit()
    _check_date(date)
    doctor = _doctor(db, doctor_id)
    duration = resolve_duration(db, doctor, type)
    slots = availability.free_slots(db, doctor, date, duration, 15, None, now=datetime.now(CLINIC_TZ))
    return {"date": date.isoformat(), "duration_min": duration, "slots": [s.astimezone(CLINIC_TZ).strftime("%H:%M") for s, _ in slots]}


def _find_patient(db: Session, phone: str, name: str, birth: date | None) -> Patient | None:
    """Mavjud bemor: shu telefon va bir xil (normallashgan) ism, yoki ism + tug'ilgan sana. Dublikat yaratilmaydi."""
    norm = normalize_name(name)
    stmt = select(Patient).where(Patient.status == StatusEnum.active, Patient.merged_into_id.is_(None), Patient.name_norm == norm)
    for p in db.scalars(stmt):
        if normalize_phone(p.phone) == phone or (birth and p.birth_date == birth):
            return p
    return None


@router.post("/public/booking", tags=[TAG], status_code=201, summary="Onlayn yozilish (telefon tasdiqlangan)",
             description="Telefon OTP bilan tasdiqlangan bo'lishi shart. Mavjud bemor topilsa qayta ishlatiladi, aks holda manba `onlayn` bilan yangi. "
                         "Oddiy qoidalar: ish vaqti, band vaqt (409). Bir telefonda 3 tadan ortiq faol qabul bo'lmaydi.")
def book_online(data: BookingIn, request: Request, db: Session = Depends(get_db)):
    _honeypot(data.website)
    phone = otp.read_verified(data.token, "booking")
    otp.rate_check(db, otp.request_ip(request), "booking_ip", 5, timedelta(hours=1))
    doctor = _doctor(db, data.doctor_id)
    day = date.fromisoformat(data.date)
    _check_date(day)
    if not db.scalar(select(AppointmentType.id).where(func.lower(AppointmentType.name) == data.type.strip().lower(), AppointmentType.is_active.is_(True))):
        raise HTTPException(422, "Xizmat topilmadi")
    branch = _branch(db)
    patient = _find_patient(db, phone, data.name, data.birth_date)
    if patient is None:
        patient = Patient(full_name=data.name.strip(), phone=phone, birth_date=data.birth_date, gender=GenderEnum.other, source="onlayn",
                          language=data.language, branch_id=branch.id)
        db.add(patient)
        db.flush()
    active = db.scalar(select(func.count()).select_from(Appointment).join(Patient, Appointment.patient_id == Patient.id).where(
        Patient.phone == phone, Appointment.status == AppointmentStatus.scheduled, Appointment.starts_at > datetime.now(UTC)))
    if active >= MAX_ACTIVE_PER_PHONE:
        raise HTTPException(409, "Bu telefon uchun faol qabullar soni limitga yetgan. Klinikaga qo'ng'iroq qiling")
    appt, violation = build_appointment(db, SystemActor(branch_id=branch.id), patient, doctor, data.date, data.time, data.type)
    if violation:
        raise HTTPException(422, violation)
    with booking_conflicts(db):
        db.flush()
        if data.consent_sms:
            set_consent(db, patient.id, Channel.sms, True, "online")
        audit.record(db, None, request, "create", "appointment", appt.id, {"via": "online", "patient_id": str(patient.id), "new_patient": patient.created_by is None})
        db.commit()
    link = links.appointment_link(appt.id, appt.starts_at)
    if data.consent_sms:
        row = db.scalar(select(ClinicSettings).where(ClinicSettings.branch_id == branch.id))
        local = appt.starts_at.astimezone(CLINIC_TZ)
        body = messaging.render(db, "booking_confirmation", patient.language, clinic=row.clinic_name if row else "Klinika", patient=(patient.full_name.split() or [""])[0],
                                doctor=doctor.full_name, date=local.strftime("%d.%m.%Y"), time=local.strftime("%H:%M"), link=link)
        messaging.enqueue(db, branch_id=branch.id, kind="booking_confirmation", body=body, patient=patient, appointment_id=appt.id,
                          dedupe_key=f"booking:{appt.id}", language=patient.language)
        db.commit()
    local = appt.starts_at.astimezone(CLINIC_TZ)
    return {"date": local.strftime("%d.%m.%Y"), "time": local.strftime("%H:%M"), "doctor": doctor.full_name, "type": data.type, "manage_link": link}
