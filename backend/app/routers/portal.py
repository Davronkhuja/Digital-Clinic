# ruff: noqa: E501
"""Bemor portali: telefon + OTP bilan kirish. Ko'rinadi: qabullar (tasdiqlash/bekor qilish), hisob-fakturalar, FAQAT shifokor tasdiqlagan
laboratoriya natijalari (PDF). EMR matni (shikoyat, tashxis, retsept) hech qachon ko'rsatilmaydi. Bir telefonda bir nechta bemor bo'lishi mumkin (oila)."""
import uuid
from datetime import UTC, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Appointment, AppointmentType, Branch, ClinicSettings, Invoice, LabOrder, Patient, Staff
from app.routers.lab import order_out
from app.routers.public import cancel_appointment
from app.routers.public_booking import MAX_ACTIVE_PER_PHONE, _branch, _check_date, _doctor
from app.schemas.enums import AppointmentStatus, InvoiceStatus, LabOrderStatus, StatusEnum
from app.services import audit, links, otp, payments, pdf
from app.services.booking import SystemActor, booking_conflicts, build_appointment
from app.services.periods import CLINIC_TZ
from app.services.phone import normalize_phone

router = APIRouter()
TAG = "🧑 Patient portal"
SESSION_TTL = timedelta(hours=2)


class PortalLoginIn(BaseModel):
    token: str


class PortalPatient(BaseModel):
    id: str
    name: str


class PortalSession(BaseModel):
    session: str
    patients: List[PortalPatient]


def _patients_of(db: Session, phone: str) -> list[Patient]:
    rows = db.scalars(select(Patient).where(Patient.status == StatusEnum.active, Patient.merged_into_id.is_(None)).order_by(Patient.full_name))
    return [p for p in rows if normalize_phone(p.phone) == phone]


def session_phone(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Kirish talab qilinadi")
    data = links.read_token(authorization[7:], "portal")
    if not data:
        raise HTTPException(401, "Seans tugagan: qayta kiring")
    return data["phone"]


def own_patient(db: Session, phone: str, patient_id: uuid.UUID) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient or normalize_phone(patient.phone) != phone or patient.status != StatusEnum.active:
        raise HTTPException(404, "Bemor topilmadi")            # boshqaning ma'lumotini ko'rsatmaymiz
    return patient


@router.post("/portal/login", tags=[TAG], response_model=PortalSession, summary="Portalga kirish (telefon OTP tasdiqlangan)",
             description="Avval `POST /public/otp/request` va `/verify` (purpose=portal), olingan `token` shu yerga. 2 soatlik seans.")
def portal_login(data: PortalLoginIn, request: Request, db: Session = Depends(get_db)):
    phone = otp.read_verified(data.token, "portal")
    patients = _patients_of(db, phone)
    if not patients:
        raise HTTPException(404, "Bu telefon raqamiga bemor topilmadi. Klinikaga murojaat qiling")
    session = links.make_token("portal", {"phone": phone}, datetime.now(UTC) + SESSION_TTL)
    audit.record(db, None, request, "login", "portal", None, {"phone_tail": phone[-4:], "patients": len(patients)})
    db.commit()
    return {"session": session, "patients": [{"id": str(p.id), "name": p.full_name} for p in patients]}


@router.get("/portal/{patient_id}/appointments", tags=[TAG], summary="Qabullar")
def portal_appointments(patient_id: uuid.UUID, request: Request, phone: str = Depends(session_phone), db: Session = Depends(get_db)):
    patient = own_patient(db, phone, patient_id)
    rows = db.scalars(select(Appointment).where(Appointment.patient_id == patient.id).order_by(Appointment.starts_at.desc()).limit(50)).all()
    now = datetime.now(UTC)
    out = []
    for a in rows:
        local = a.starts_at.astimezone(CLINIC_TZ)
        out.append({"id": str(a.id), "date": local.strftime("%d.%m.%Y"), "time": local.strftime("%H:%M"), "doctor": db.get(Staff, a.doctor_id).full_name,
                    "branch_id": str(a.branch_id), "branch": db.get(Branch, a.branch_id).name, "type": a.type, "status": a.status.value, "confirmed": a.confirmed_at is not None,
                    "can_act": a.status == AppointmentStatus.scheduled and a.starts_at > now})
    audit.record(db, None, request, "read", "appointment", None, {"via": "portal", "patient_id": str(patient.id), "count": len(out)})
    db.commit()
    return out


class PortalBookingIn(BaseModel):
    branch_id: Optional[str] = None
    doctor_id: str
    type: str
    date: str
    time: str


@router.post("/portal/{patient_id}/appointments", tags=[TAG], status_code=201, summary="Yangi qabulga yozilish (filial tanlab)",
             description="Bemor portalida: filial, xizmat, shifokor, sana va vaqt tanlanadi (bo'sh vaqtlar `/public/booking/slots?branch_id=`). "
                         "Oddiy qoidalar: shifokor shu filialda ishlashi, ish vaqti, band vaqt (409); bir telefonda 3 tadan ortiq faol qabul bo'lmaydi.")
def portal_book(patient_id: uuid.UUID, data: PortalBookingIn, request: Request, phone: str = Depends(session_phone), db: Session = Depends(get_db)):
    patient = own_patient(db, phone, patient_id)
    otp.rate_check(db, otp.request_ip(request), "portal_booking_ip", 10, timedelta(hours=1))
    branch = _branch(db, data.branch_id)
    doctor = _doctor(db, data.doctor_id)
    try:
        day = datetime.strptime(data.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, "Sana noto'g'ri")
    _check_date(day)
    if not db.scalar(select(AppointmentType.id).where(func.lower(AppointmentType.name) == data.type.strip().lower(), AppointmentType.is_active.is_(True))):
        raise HTTPException(422, "Xizmat topilmadi")
    active = db.scalar(select(func.count()).select_from(Appointment).where(
        Appointment.patient_id == patient.id, Appointment.status == AppointmentStatus.scheduled, Appointment.starts_at > datetime.now(UTC)))
    if active >= MAX_ACTIVE_PER_PHONE:
        raise HTTPException(409, "Faol qabullar soni limitga yetgan. Klinikaga qo'ng'iroq qiling")
    appt, violation = build_appointment(db, SystemActor(branch_id=branch.id), patient, doctor, data.date, data.time, data.type)
    if violation:
        raise HTTPException(422, violation)
    with booking_conflicts(db):
        db.flush()
        audit.record(db, None, request, "create", "appointment", appt.id, {"via": "portal", "patient_id": str(patient.id), "branch_id": str(branch.id)})
        db.commit()
    local = appt.starts_at.astimezone(CLINIC_TZ)
    return {"id": str(appt.id), "date": local.strftime("%d.%m.%Y"), "time": local.strftime("%H:%M"), "doctor": doctor.full_name, "branch": branch.name,
            "type": data.type}


def _act(db: Session, phone: str, patient_id: uuid.UUID, appt_id: uuid.UUID) -> Appointment:
    own_patient(db, phone, patient_id)
    appt = db.scalar(select(Appointment).where(Appointment.id == appt_id, Appointment.patient_id == patient_id).with_for_update())
    if not appt:
        raise HTTPException(404, "Qabul topilmadi")
    if appt.status != AppointmentStatus.scheduled or appt.starts_at <= datetime.now(UTC):
        raise HTTPException(409, "Qabul faol emas")
    return appt


@router.post("/portal/{patient_id}/appointments/{appt_id}/confirm", tags=[TAG], summary="Qabulni tasdiqlash")
def portal_confirm(patient_id: uuid.UUID, appt_id: uuid.UUID, request: Request, phone: str = Depends(session_phone), db: Session = Depends(get_db)):
    appt = _act(db, phone, patient_id, appt_id)
    appt.confirmed_at = appt.confirmed_at or datetime.now(UTC)
    audit.record(db, None, request, "update", "appointment", appt.id, {"confirmed": True, "via": "portal", "patient_id": str(patient_id)})
    db.commit()
    return {"confirmed": True}


@router.post("/portal/{patient_id}/appointments/{appt_id}/cancel", tags=[TAG], summary="Qabulni bekor qilish (vaqt bo'shaydi, kutuvchiga taklif)")
def portal_cancel(patient_id: uuid.UUID, appt_id: uuid.UUID, request: Request, phone: str = Depends(session_phone), db: Session = Depends(get_db)):
    appt = _act(db, phone, patient_id, appt_id)
    cancel_appointment(db, appt, "portal", request)
    return {"status": "Cancelled"}


@router.get("/portal/{patient_id}/invoices", tags=[TAG], summary="Hisob-fakturalar")
def portal_invoices(patient_id: uuid.UUID, request: Request, phone: str = Depends(session_phone), db: Session = Depends(get_db)):
    patient = own_patient(db, phone, patient_id)
    rows = db.scalars(select(Invoice).where(Invoice.patient_id == patient.id, Invoice.status != InvoiceStatus.draft).order_by(Invoice.created_at.desc()).limit(50)).all()
    out = []
    for inv in rows:
        paid, refunded = payments.invoice_paid_refunded(db, inv.id)
        out.append({"id": str(inv.id), "number": inv.number, "date": inv.created_at.astimezone(CLINIC_TZ).strftime("%d.%m.%Y"), "status": inv.status.value,
                    "total": float(inv.total), "paid": float(paid - refunded), "insurer_total": float(inv.insurer_total), "balance": float(inv.total - inv.insurer_total - (paid - refunded)) if inv.status != InvoiceStatus.cancelled else 0.0})
    audit.record(db, None, request, "read", "invoice", None, {"via": "portal", "patient_id": str(patient.id), "count": len(out)})
    db.commit()
    return out


def _approved_orders(db: Session, patient_id: uuid.UUID) -> list[LabOrder]:
    return list(db.scalars(select(LabOrder).where(LabOrder.patient_id == patient_id, LabOrder.status == LabOrderStatus.completed,
                                                  LabOrder.approved_at.is_not(None)).order_by(LabOrder.created_at.desc()).limit(50)))


@router.get("/portal/{patient_id}/lab-results", tags=[TAG], summary="Laboratoriya natijalari (faqat shifokor tasdiqlaganlari)")
def portal_lab_results(patient_id: uuid.UUID, request: Request, phone: str = Depends(session_phone), db: Session = Depends(get_db)):
    patient = own_patient(db, phone, patient_id)
    out = []
    for o in _approved_orders(db, patient.id):
        full = order_out(db, o)
        out.append({"id": full["id"], "date": full["created_at"][:10], "doctor": full["doctor"], "items": [
            {"name": i["name"], "value": i["value"], "unit": i["unit"], "reference": i["reference"], "flag": i["flag"]} for i in full["items"]]})
    audit.record(db, None, request, "read", "lab_order", None, {"via": "portal", "patient_id": str(patient.id), "count": len(out)})
    db.commit()
    return out


@router.get("/portal/{patient_id}/lab-results/{order_id}/pdf", tags=[TAG], summary="Natija PDF (faqat tasdiqlangan)", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def portal_lab_pdf(patient_id: uuid.UUID, order_id: uuid.UUID, request: Request, phone: str = Depends(session_phone), db: Session = Depends(get_db)):
    patient = own_patient(db, phone, patient_id)
    order = db.get(LabOrder, order_id)
    if not order or order.patient_id != patient.id or order.approved_at is None or order.status != LabOrderStatus.completed:
        raise HTTPException(404, "Natija topilmadi yoki hali tasdiqlanmagan")
    clinic = db.scalar(select(ClinicSettings).where(ClinicSettings.branch_id == order.branch_id))
    content = pdf.lab_order_pdf(order_out(db, order), {"name": patient.full_name, "birth_date": patient.birth_date.isoformat() if patient.birth_date else None,
                                                        "gender": patient.gender.value},
                                {"name": clinic.clinic_name if clinic else None, "address": clinic.address if clinic else None, "phone": clinic.phone if clinic else None})
    audit.record(db, None, request, "read", "lab_order", order.id, {"via": "portal", "pdf": True, "patient_id": str(patient.id)})
    db.commit()
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="natija-{str(order.id)[:8]}.pdf"',
                                                                    "Cache-Control": "private, no-store"})
