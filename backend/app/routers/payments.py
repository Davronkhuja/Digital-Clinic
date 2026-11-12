import uuid
from datetime import UTC, datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Invoice, Payment, PaymentRefund, Staff, User
from app.schemas.enums import InvoiceStatus, PaymentMethod, PaymentStatus, ReceiptStatus
from app.schemas.payments import PaymentCreate, PaymentOut, RefundCreate
from app.services import audit, fiscal, payme, payments
from app.services.money import q2
from app.services.periods import CLINIC_TZ

router = APIRouter()
TAG = "💳 Payments"
CASHIER_METHODS = (PaymentMethod.cash, PaymentMethod.card)
ONLINE_METHODS = (PaymentMethod.payme,)  # Click v1.7.4 da


def _refund_out(r: PaymentRefund) -> dict:
    return {"id": str(r.id), "payment_id": str(r.payment_id), "amount": r.amount, "reason": r.reason,
            "receipt_status": r.receipt_status, "receipt_id": r.receipt_id, "created_at": r.created_at.astimezone(CLINIC_TZ).isoformat()}


def payment_out(db: Session, p: Payment) -> dict:
    checkout_url = payme.checkout_url(p) if p.method == PaymentMethod.payme and p.status == PaymentStatus.pending else None
    inv = db.get(Invoice, p.invoice_id)
    refunds = list(db.scalars(select(PaymentRefund).where(PaymentRefund.payment_id == p.id).order_by(PaymentRefund.created_at)))
    who = db.scalar(select(Staff.full_name).join(User, User.staff_id == Staff.id).where(User.id == p.created_by)) if p.created_by else None
    return {"id": str(p.id), "invoice_id": str(p.invoice_id), "invoice_number": inv.number, "method": p.method, "status": p.status,
            "amount": p.amount, "refunded_amount": q2(sum((r.amount for r in refunds), 0)), "reference": p.reference,
            "provider_txn_id": p.provider_txn_id, "receipt_status": p.receipt_status, "receipt_id": p.receipt_id,
            "checkout_url": checkout_url, "paid_at": p.paid_at, "created_by": who,
            "created_at": p.created_at.astimezone(CLINIC_TZ).isoformat(), "refunds": [_refund_out(r) for r in refunds]}


def _invoice(db: Session, invoice_id: uuid.UUID) -> Invoice:
    inv = db.get(Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "Hisob-faktura topilmadi")
    return inv


@router.post("/invoices/{invoice_id}/payments", tags=[TAG], response_model=PaymentOut, status_code=201,
             summary="Kassada to'lov qabul qilish (naqd/karta)",
             description="Hisob-faktura `Issued`/`PartiallyPaid` bo'lishi, summa qoldiqdan oshmasligi kerak. To'lov fiskal chek bilan "
                         "yopiladi (chek berilmasa to'lov yozilmaydi, 502). Daromad yozuvi avtomatik. Click/Payme alohida oqimda.")
def create_payment(invoice_id: uuid.UUID, data: PaymentCreate, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("finance:write"))):
    inv = _invoice(db, invoice_id)
    if data.method not in CASHIER_METHODS + ONLINE_METHODS:
        raise HTTPException(422, "To'lov usuli hozircha qo'llab-quvvatlanmaydi")
    if inv.status not in (InvoiceStatus.issued, InvoiceStatus.partially_paid):
        raise HTTPException(409, "To'lov faqat chiqarilgan (Issued) yoki qisman to'langan hisob-fakturaga qabul qilinadi")
    balance = payments.available_balance(db, inv)
    amount = q2(data.amount) if data.amount is not None else balance
    if amount <= 0:
        raise HTTPException(409, "To'lanadigan qoldiq yo'q")
    if amount > balance:
        raise HTTPException(422, f"Summa qoldiqdan katta (qoldiq: {balance})")
    if data.method in ONLINE_METHODS and not settings.payme_merchant_id:
        raise HTTPException(503, "Payme sozlanmagan (PAYME_MERCHANT_ID .env da)")
    p = Payment(invoice_id=inv.id, method=data.method, status=PaymentStatus.pending, amount=amount, reference=data.reference,
                branch_id=user.branch_id, created_by=user.id)
    db.add(p)
    db.flush()
    if data.method in ONLINE_METHODS:  # onlayn: pul provayder chaqiruvi bilan keladi; summa qoldiqdan band qilinadi
        audit.record(db, user, request, "create", "payment", p.id, {"invoice": inv.number, "method": p.method.value,
                                                                     "amount": str(amount), "status": "Pending"})
        db.commit()
        return payment_out(db, p)
    try:
        payments.mark_paid(db, p, inv, user.id, strict_receipt=True)
    except fiscal.FiscalError:
        db.rollback()
        raise HTTPException(502, "Fiskal chek berilmadi: to'lov yozilmadi, qayta urinib ko'ring")
    audit.record(db, user, request, "create", "payment", p.id, {"invoice": inv.number, "method": p.method.value, "amount": str(amount),
                                                                 "receipt_id": p.receipt_id})
    db.commit()
    return payment_out(db, p)


@router.get("/invoices/{invoice_id}/payments", tags=[TAG], response_model=List[PaymentOut], summary="Hisob-faktura to'lovlari")
def list_invoice_payments(invoice_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(require("finance:read"))):
    _invoice(db, invoice_id)
    rows = db.scalars(select(Payment).where(Payment.invoice_id == invoice_id).order_by(Payment.created_at))
    result = [payment_out(db, p) for p in rows]
    audit.record_read(db, user, request, "payment", details={"invoice_id": str(invoice_id), "count": len(result)})
    return result


@router.post("/payments/{payment_id}/receipt", tags=[TAG], response_model=PaymentOut, summary="Chekni qayta berish",
             description="Provayder pulni olgan, lekin fiskal chek berilmagan (`receipt_status=Failed`/`Pending`) to'lov uchun.")
def retry_receipt(payment_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require("finance:write"))):
    p = db.get(Payment, payment_id)
    if not p:
        raise HTTPException(404, "To'lov topilmadi")
    if p.status != PaymentStatus.paid or p.receipt_status == ReceiptStatus.issued:
        raise HTTPException(409, "Chek kerak emas: to'lov to'lanmagan yoki chek allaqachon berilgan")
    try:
        payments.issue_payment_receipt(db, p, db.get(Invoice, p.invoice_id), strict=True)
    except fiscal.FiscalError:
        db.rollback()
        raise HTTPException(502, "Fiskal chek berilmadi, keyinroq qayta urinib ko'ring")
    audit.record(db, user, request, "update", "payment", p.id, {"receipt_id": p.receipt_id})
    db.commit()
    return payment_out(db, p)


@router.post("/payments/{payment_id}/cancel", tags=[TAG], response_model=PaymentOut, summary="Kutilayotgan onlayn to'lovni bekor qilish",
             description="Faqat `Pending` va provayder tranzaksiyasi boshlanmagan to'lov (summa qoldiqqa qaytadi).")
def cancel_pending_payment(payment_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(require("finance:write"))):
    p = db.get(Payment, payment_id)
    if not p:
        raise HTTPException(404, "To'lov topilmadi")
    if p.status != PaymentStatus.pending or p.provider_state is not None:
        raise HTTPException(409, "Faqat provayder tranzaksiyasi boshlanmagan kutilayotgan to'lovni bekor qilish mumkin")
    p.status, p.cancelled_at = PaymentStatus.cancelled, datetime.now(UTC)
    audit.record(db, user, request, "update", "payment", p.id, {"status": "Cancelled"})
    db.commit()
    return payment_out(db, p)


@router.post("/payments/{payment_id}/refunds", tags=[TAG], response_model=PaymentOut, status_code=201,
             summary="To'lovni qaytarish (naqd/karta)",
             description="`finance:refund` ruxsati, sabab majburiy. Qaytarish cheki fiskal, xarajat yozuvi avtomatik; hisob-faktura holati "
                         "qayta hisoblanadi. Click/Payme to'lovi provayder orqali qaytariladi.")
def refund_payment(payment_id: uuid.UUID, data: RefundCreate, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("finance:refund"))):
    p = db.get(Payment, payment_id)
    if not p:
        raise HTTPException(404, "To'lov topilmadi")
    if p.method not in CASHIER_METHODS:
        raise HTTPException(409, "Click/Payme to'lovi provayder orqali qaytariladi (provayder bekor qilishi bilan avtomatik yoziladi)")
    inv = db.get(Invoice, p.invoice_id)
    amount = q2(data.amount) if data.amount is not None else payments.refundable(db, p)
    try:
        refund = payments.create_refund(db, p, inv, amount, data.reason.strip(), user)
    except fiscal.FiscalError:
        db.rollback()
        raise HTTPException(502, "Qaytarish cheki berilmadi: qaytarish yozilmadi, qayta urinib ko'ring")
    audit.record(db, user, request, "refund", "payment", p.id, {"invoice": inv.number, "amount": str(amount), "reason": data.reason.strip(),
                                                                 "refund_id": str(refund.id), "receipt_id": refund.receipt_id})
    db.commit()
    return payment_out(db, p)


