# ruff: noqa: E501
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Appointment, Encounter, Invoice, InvoiceLine, Patient, Service, Staff
from app.models.invoice import invoice_number_seq
from app.schemas.enums import AppointmentStatus, InvoiceStatus, StaffRole
from app.schemas.invoices import CancelIn, InvoiceCreate, InvoiceLineIn, InvoiceOut, InvoiceUpdate
from app.services import app_settings, audit, invoicing, payments, warehouse
from app.services.lookup import get_patient_or_404
from app.services.money import q2
from app.services.periods import CLINIC_TZ

router = APIRouter()
TAG = "🧾 Invoices"
DISCOUNT_PERM = "finance:discount"
OVERRIDE_PERM = "finance:discount_override"


def invoice_out(db: Session, inv: Invoice) -> dict:
    patient = db.get(Patient, inv.patient_id)
    doctor = db.get(Staff, inv.doctor_id) if inv.doctor_id else None
    rows = db.execute(select(InvoiceLine, Staff.full_name).outerjoin(Staff, InvoiceLine.doctor_id == Staff.id)
                      .where(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.position)).all()
    paid, refunded = payments.invoice_paid_refunded(db, inv.id)
    return {
        "id": str(inv.id), "number": inv.number, "patient_id": str(inv.patient_id), "patient_name": patient.full_name,
        "doctor_id": str(inv.doctor_id) if inv.doctor_id else None, "doctor": doctor.full_name if doctor else None,
        "appointment_id": str(inv.appointment_id) if inv.appointment_id else None,
        "encounter_id": str(inv.encounter_id) if inv.encounter_id else None, "status": inv.status, "subtotal": inv.subtotal,
        "discount_total": inv.discount_total, "total": inv.total, "vat_total": inv.vat_total,
        "discount_percent": inv.discount_percent, "discount_reason": inv.discount_reason, "notes": inv.notes,
        "paid_amount": paid, "refunded_amount": refunded, "balance": inv.total - (paid - refunded),
        "issued_at": inv.issued_at, "cancelled_at": inv.cancelled_at, "cancel_reason": inv.cancel_reason,
        "created_at": inv.created_at.astimezone(CLINIC_TZ).isoformat(),
        "lines": [{"id": str(ln.id), "service_id": str(ln.service_id), "name": ln.name, "mxik": ln.mxik, "package_code": ln.package_code,
                   "vat_percent": ln.vat_percent, "unit_price": ln.unit_price, "quantity": ln.quantity,
                   "doctor_id": str(ln.doctor_id) if ln.doctor_id else None, "doctor": name, "line_discount": ln.line_discount,
                   "invoice_discount_share": ln.invoice_discount_share, "net_total": ln.net_total, "vat_amount": ln.vat_amount,
                   "performed_at": ln.performed_at}
                  for ln, name in rows],
    }


def _perform_if_completed(db: Session, inv: Invoice, user: CurrentUser) -> None:
    """Qabul allaqachon yakunlangan bo'lsa, hisob-faktura chiqarilishi bilan xizmatlar bajarilgan hisoblanadi."""
    if inv.appointment_id:
        appt = db.get(Appointment, inv.appointment_id)
        if appt and appt.status == AppointmentStatus.completed:
            db.flush()
            warehouse.perform_invoice(db, inv, user.id)


def _doctor(db: Session, doctor_id: uuid.UUID | None) -> Staff | None:
    if not doctor_id:
        return None
    doctor = db.get(Staff, doctor_id)
    if not doctor or doctor.role != StaffRole.doctor:
        raise HTTPException(422, "Shifokor topilmadi")
    return doctor


def _build_lines(db: Session, lines: list[InvoiceLineIn], default_doctor: uuid.UUID | None, branch_id: uuid.UUID) -> list[invoicing.LineInput]:
    services = {s.id: s for s in db.scalars(select(Service).where(Service.id.in_({ln.service_id for ln in lines})))}
    missing = {ln.service_id for ln in lines} - services.keys()
    if missing:
        raise HTTPException(422, f"Xizmat topilmadi: {', '.join(str(m) for m in missing)}")
    invoicing.require_sellable(services)
    prices = invoicing.branch_prices(db, branch_id, services.keys())          # filial narxi bo'lsa shu, aks holda asosiy narx
    inputs = []
    for ln in lines:
        _doctor(db, ln.doctor_id)
        inputs.append(invoicing.LineInput(services[ln.service_id], ln.quantity, ln.doctor_id or default_doctor,
                                          ln.discount_percent, ln.discount_amount, prices.get(ln.service_id)))
    return inputs


def _check_discount(db: Session, user: CurrentUser, computed: invoicing.Computed, reason: str | None) -> None:
    """Chegirma bor bo'lsa: `finance:discount`, sabab majburiy; umumiy chegirma foizi sozlamadagi limitdan oshsa
    `finance:discount_override`. Foiz = jami chegirma / chegirmasiz summa."""
    if computed.discount_total <= 0:
        return
    if DISCOUNT_PERM not in user.permissions:
        raise HTTPException(403, f"Chegirma berish uchun ruxsat yo'q ({DISCOUNT_PERM})")
    if len((reason or "").strip()) < 3:
        raise HTTPException(422, "Chegirma sababi majburiy")
    limit = app_settings.discount_limit(db, user.branch_id)
    percent = computed.discount_total * 100 / computed.subtotal if computed.subtotal else Decimal("0")  # yaxlitlamasdan solishtiriladi
    if percent > limit and OVERRIDE_PERM not in user.permissions:
        raise HTTPException(403, f"Chegirma {q2(percent)}% limit ({limit}%) dan oshadi: {OVERRIDE_PERM} ruxsati kerak")


def _write_lines(db: Session, inv: Invoice, computed: invoicing.Computed, user: CurrentUser) -> None:
    for pos, c in enumerate(computed.lines):
        db.add(InvoiceLine(invoice_id=inv.id, service_id=c.service.id, doctor_id=c.doctor_id, position=pos, name=c.service.name,
                           mxik=c.service.mxik, package_code=c.service.package_code, vat_percent=c.service.vat_percent,
                           unit_price=c.unit_price, quantity=c.quantity, line_discount=c.line_discount,
                           invoice_discount_share=c.invoice_discount_share, net_total=c.net_total, vat_amount=c.vat_amount,
                           created_by=user.id))
    inv.subtotal, inv.discount_total = computed.subtotal, computed.discount_total
    inv.total, inv.vat_total = computed.total, computed.vat_total


def _get(db: Session, invoice_id: uuid.UUID) -> Invoice:
    inv = db.get(Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "Hisob-faktura topilmadi")
    return inv


@router.post("/invoices", tags=[TAG], response_model=InvoiceOut, status_code=201, summary="Hisob-faktura yaratish",
             description="Faqat sotiladigan xizmatlar (MXIK, package_code, QQS to'liq). Chegirma `finance:discount` va sabab bilan. "
                         "Narx va soliq maydonlari qatorga nusxalanadi. `issue=true`: darhol `Issued`.")
def create_invoice(data: InvoiceCreate, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("finance:write"))):
    patient = get_patient_or_404(db, data.patient_id)
    doctor = _doctor(db, data.doctor_id)
    if data.appointment_id:
        appt = db.get(Appointment, data.appointment_id)
        if not appt or appt.patient_id != patient.id:
            raise HTTPException(422, "Qabul topilmadi yoki boshqa bemorga tegishli")
        doctor = doctor or db.get(Staff, appt.doctor_id)
        if db.scalar(select(Invoice.id).where(Invoice.appointment_id == appt.id, Invoice.status != InvoiceStatus.cancelled).limit(1)):
            raise HTTPException(409, "Bu qabul uchun hisob-faktura allaqachon mavjud")
    if data.encounter_id:
        enc = db.get(Encounter, data.encounter_id)
        if not enc or enc.deleted_at is not None or enc.patient_id != patient.id:
            raise HTTPException(422, "Ko'rik topilmadi yoki boshqa bemorga tegishli")
    computed = invoicing.compute(_build_lines(db, data.lines, doctor.id if doctor else None, user.branch_id), data.discount_percent,
                                  data.discount_amount)
    _check_discount(db, user, computed, data.discount_reason)
    number = f"INV-{db.scalar(select(invoice_number_seq.next_value())):06d}"
    inv = Invoice(number=number, patient_id=patient.id, doctor_id=doctor.id if doctor else None, appointment_id=data.appointment_id,
                  encounter_id=data.encounter_id, status=InvoiceStatus.issued if data.issue else InvoiceStatus.draft,
                  issued_at=datetime.now(UTC) if data.issue else None, discount_percent=data.discount_percent,
                  discount_reason=(data.discount_reason or "").strip() or None, notes=data.notes, branch_id=user.branch_id,
                  created_by=user.id)
    db.add(inv)
    db.flush()
    _write_lines(db, inv, computed, user)
    if data.issue:
        _perform_if_completed(db, inv, user)
    audit.record(db, user, request, "create", "invoice", inv.id,
                 {"number": number, "patient_id": str(patient.id), "total": str(inv.total), "discount": str(inv.discount_total),
                  "status": inv.status.value})
    db.commit()
    return invoice_out(db, inv)


@router.get("/invoices", tags=[TAG], response_model=List[InvoiceOut], summary="Hisob-fakturalar")
def list_invoices(request: Request, patient_id: Optional[uuid.UUID] = None, status: Optional[InvoiceStatus] = None,
                  number: Optional[str] = None, limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require("finance:read"))):
    stmt = select(Invoice).where(Invoice.branch_id == user.branch_id).order_by(Invoice.created_at.desc()).limit(limit)
    if patient_id:
        stmt = stmt.where(Invoice.patient_id == patient_id)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if number:
        stmt = stmt.where(Invoice.number.ilike(f"%{number.strip()}%"))
    result = [invoice_out(db, i) for i in db.scalars(stmt)]
    audit.record_read(db, user, request, "invoice", details={"count": len(result)})
    return result


@router.get("/invoices/{invoice_id}", tags=[TAG], response_model=InvoiceOut, summary="Bitta hisob-faktura")
def get_invoice(invoice_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require("finance:read"))):
    inv = _get(db, invoice_id)
    audit.record_read(db, user, request, "invoice", inv.id, {"number": inv.number})
    return invoice_out(db, inv)


@router.put("/invoices/{invoice_id}", tags=[TAG], response_model=InvoiceOut, summary="Qoralamani o'zgartirish",
            description="Faqat `Draft`: qatorlar va chegirmalar to'liq almashtiriladi.")
def update_invoice(invoice_id: uuid.UUID, data: InvoiceUpdate, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("finance:write"))):
    inv = _get(db, invoice_id)
    if inv.status != InvoiceStatus.draft:
        raise HTTPException(409, "Faqat qoralama (Draft) hisob-fakturani o'zgartirish mumkin")
    doctor = _doctor(db, data.doctor_id) or (db.get(Staff, inv.doctor_id) if inv.doctor_id else None)
    computed = invoicing.compute(_build_lines(db, data.lines, doctor.id if doctor else None, inv.branch_id), data.discount_percent,
                                  data.discount_amount)
    _check_discount(db, user, computed, data.discount_reason)
    for old in db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)):
        db.delete(old)
    db.flush()
    inv.doctor_id = doctor.id if doctor else None
    inv.discount_percent, inv.discount_reason, inv.notes = data.discount_percent, (data.discount_reason or "").strip() or None, data.notes
    _write_lines(db, inv, computed, user)
    audit.record(db, user, request, "update", "invoice", inv.id,
                 {"number": inv.number, "total": str(inv.total), "discount": str(inv.discount_total)})
    db.commit()
    return invoice_out(db, inv)


@router.post("/invoices/{invoice_id}/issue", tags=[TAG], response_model=InvoiceOut, summary="Hisob-fakturani chiqarish (qatorlar qotadi)")
def issue_invoice(invoice_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require("finance:write"))):
    inv = _get(db, invoice_id)
    if inv.status != InvoiceStatus.draft:
        raise HTTPException(409, "Faqat qoralamani chiqarish mumkin")
    inv.status, inv.issued_at = InvoiceStatus.issued, datetime.now(UTC)
    _perform_if_completed(db, inv, user)
    audit.record(db, user, request, "update", "invoice", inv.id, {"number": inv.number, "status": "Issued", "total": str(inv.total)})
    db.commit()
    return invoice_out(db, inv)


@router.post("/invoices/{invoice_id}/cancel", tags=[TAG], response_model=InvoiceOut, summary="Hisob-fakturani bekor qilish",
             description="To'lovi yo'q (`Draft`/`Issued`) hisob-faktura; sabab majburiy. To'langanini qaytarish orqali (refund).")
def cancel_invoice(invoice_id: uuid.UUID, data: CancelIn, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("finance:write"))):
    inv = _get(db, invoice_id)
    if inv.status not in (InvoiceStatus.draft, InvoiceStatus.issued):
        raise HTTPException(409, "To'lovi bor yoki bekor qilingan hisob-fakturani bekor qilib bo'lmaydi (qaytarishdan foydalaning)")
    if payments.has_payments(db, inv.id):
        raise HTTPException(409, "To'lovi bor hisob-fakturani bekor qilib bo'lmaydi (qaytarishdan foydalaning)")
    inv.status, inv.cancelled_at, inv.cancel_reason = InvoiceStatus.cancelled, datetime.now(UTC), data.reason.strip()
    audit.record(db, user, request, "update", "invoice", inv.id, {"number": inv.number, "status": "Cancelled", "reason": inv.cancel_reason})
    db.commit()
    return invoice_out(db, inv)


def _line(db: Session, invoice_id: uuid.UUID, line_id: uuid.UUID) -> tuple[Invoice, InvoiceLine]:
    inv = _get(db, invoice_id)
    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != inv.id:
        raise HTTPException(404, "Qator topilmadi")
    return inv, line


@router.post("/invoices/{invoice_id}/lines/{line_id}/perform", tags=[TAG], response_model=InvoiceOut, summary="Xizmat bajarildi (sarf ombordan yoziladi)",
             description="Qatorning sarf normasi x miqdori FEFO bo'yicha ombordan yoziladi. Chiqarilgan hisob-faktura kerak; to'liq qaytarilgan hisob-fakturada "
                         "bajarib bo'lmaydi. Qabul `Completed` bo'lganda bog'langan hisob-faktura qatorlari avtomatik bajarilgan bo'ladi. "
                         "Ombor yetmasa belgi qo'yiladi, qoldiq manfiyga tushmaydi, yetmagani yetishmovchilik ro'yxatiga tushadi.")
def perform_line(invoice_id: uuid.UUID, line_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require("appointments:write"))):
    inv, line = _line(db, invoice_id, line_id)
    if inv.status in (InvoiceStatus.draft, InvoiceStatus.cancelled):
        raise HTTPException(409, "Faqat chiqarilgan hisob-faktura xizmati bajarilgan bo'ladi")
    paid, refunded = payments.invoice_paid_refunded(db, inv.id)
    if refunded > 0 and paid - refunded <= 0:
        raise HTTPException(409, "To'liq qaytarilgan hisob-fakturada xizmat bajarilmaydi")
    if line.performed_at is not None:
        raise HTTPException(409, "Xizmat allaqachon bajarilgan")
    res = warehouse.perform_line(db, inv, line, user.id)
    audit.record(db, user, request, "update", "invoice", inv.id, {"number": inv.number, "perform_line": str(line.id), **res})
    db.commit()
    return invoice_out(db, inv)


@router.delete("/invoices/{invoice_id}/lines/{line_id}/perform", tags=[TAG], response_model=InvoiceOut, summary="Bajarildi belgisini qaytarish",
               description="Xato belgilangan xizmat: yozilgan sarf o'z partiyalariga qaytadi, ochiq yetishmovchilik yopiladi. Bajarilgan xizmat qaytarilsa (pul) material qaytmaydi.")
def unperform_line(invoice_id: uuid.UUID, line_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("appointments:write"))):
    inv, line = _line(db, invoice_id, line_id)
    if line.performed_at is None:
        raise HTTPException(409, "Xizmat bajarilgan deb belgilanmagan")
    warehouse.unperform_line(db, inv, line, user.id)
    audit.record(db, user, request, "update", "invoice", inv.id, {"number": inv.number, "unperform_line": str(line.id)})
    db.commit()
    return invoice_out(db, inv)
