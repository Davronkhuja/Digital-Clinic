# ruff: noqa: E501
"""To'lovlar: summa taqsimlash, fiskal chek, tranzaksiya (daromad/xarajat), hisob-faktura holati, qaytarish."""
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.models import Invoice, InvoiceLine, Payment, PaymentRefund, Transaction
from app.schemas.enums import InvoiceStatus, PaymentMethod, PaymentStatus, ReceiptStatus, TransactionType
from app.services import commissions, fiscal
from app.services.invoicing import allocate
from app.services.money import q2, to_tiyin
from app.services.periods import clinic_today

ZERO = Decimal("0.00")


def _sum_payments(db: Session, invoice_id: uuid.UUID, status: PaymentStatus) -> Decimal:
    stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == invoice_id, Payment.status == status)
    return q2(db.scalar(stmt))


def invoice_paid_refunded(db: Session, invoice_id: uuid.UUID) -> tuple[Decimal, Decimal]:
    paid = _sum_payments(db, invoice_id, PaymentStatus.paid)
    refunded = db.scalar(select(func.coalesce(func.sum(PaymentRefund.amount), 0)).join(Payment, PaymentRefund.payment_id == Payment.id)
                         .where(Payment.invoice_id == invoice_id))
    return paid, q2(refunded)


def pending_amount(db: Session, invoice_id: uuid.UUID) -> Decimal:
    return _sum_payments(db, invoice_id, PaymentStatus.pending)


def has_payments(db: Session, invoice_id: uuid.UUID) -> bool:
    live = [PaymentStatus.paid, PaymentStatus.pending]
    return bool(db.scalar(select(Payment.id).where(Payment.invoice_id == invoice_id, Payment.status.in_(live)).limit(1)))


def available_balance(db: Session, inv: Invoice) -> Decimal:
    """To'lash mumkin bo'lgan qoldiq: total - (to'langan - qaytarilgan) - kutilayotgan (Click/Payme) summalar."""
    paid, refunded = invoice_paid_refunded(db, inv.id)
    return q2(inv.total - inv.insurer_total - (paid - refunded) - pending_amount(db, inv.id))     # bemor ulushi (sug'urta ulushi kompaniyadan keladi)


def recompute_status(db: Session, inv: Invoice) -> None:
    if inv.status in (InvoiceStatus.draft, InvoiceStatus.cancelled):
        return
    paid, refunded = invoice_paid_refunded(db, inv.id)
    net = paid - refunded
    if net >= inv.total - inv.insurer_total and inv.total > 0:     # bemor ulushi to'langan
        inv.status = InvoiceStatus.paid
    else:
        inv.status = InvoiceStatus.partially_paid if net > 0 else InvoiceStatus.issued


def build_receipt(inv: Invoice, lines: list[InvoiceLine], amount: Decimal, method: PaymentMethod, kind: str) -> dict:
    """Fiskal chek ma'lumoti (tiyinda). Har qator: nom, MXIK, package_code, QQS foizi va summasi (to'lov ulushi)."""
    items = []
    for ln, share in allocate(lines, amount):
        if share <= 0:
            continue
        vat = q2(share * ln.vat_percent / (100 + ln.vat_percent))
        items.append({"title": ln.name, "mxik": ln.mxik, "package_code": ln.package_code, "count": ln.quantity,
                      "amount_tiyin": to_tiyin(share), "vat_percent": float(ln.vat_percent), "vat_tiyin": to_tiyin(vat)})
    total = to_tiyin(amount)
    pay = {"cash_tiyin": total if method == PaymentMethod.cash else 0, "card_tiyin": total if method == PaymentMethod.card else 0,
           "other_tiyin": total if method in (PaymentMethod.click, PaymentMethod.payme) else 0}
    return {"type": kind, "invoice": inv.number, "time": datetime.now(UTC).isoformat(), "items": items, "payment": pay,
            "total_tiyin": total}


def issue_payment_receipt(db: Session, payment: Payment, inv: Invoice, strict: bool) -> None:
    """Chek beradi va `receipt_id` ni saqlaydi. strict=True (kassada): xato bo'lsa FiscalError ko'tariladi;
    aks holda (provayder allaqachon pulni olgan) `receipt_status=Failed`, keyin qayta urinish mumkin."""
    lines = list(db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.position)))
    receipt = build_receipt(inv, lines, payment.amount, payment.method, "sale")
    payment.receipt_data = receipt
    try:
        result = fiscal.get_fiscal().sale(receipt)
    except fiscal.FiscalError:
        if strict:
            raise
        payment.receipt_status = ReceiptStatus.failed
        return
    payment.receipt_id, payment.receipt_status = result.receipt_id, ReceiptStatus.issued
    payment.receipt_data = {**receipt, "fiscal_sign": result.fiscal_sign, "qr_url": result.qr_url}


def record_income(db: Session, payment: Payment, inv: Invoice, user_id: uuid.UUID | None) -> None:
    db.add(Transaction(type=TransactionType.income, amount=payment.amount, category="Xizmat to'lovi", date=clinic_today(),
                       description=f"Hisob-faktura {inv.number} ({payment.method.value})", patient_id=inv.patient_id,
                       payment_id=payment.id, branch_id=payment.branch_id, created_by=user_id))


def mark_paid(db: Session, payment: Payment, inv: Invoice, user_id: uuid.UUID | None, strict_receipt: bool) -> None:
    """Pending/yangi to'lovni `Paid` qiladi: chek, daromad yozuvi, hisob-faktura holati (bitta tranzaksiyada)."""
    payment.status, payment.paid_at = PaymentStatus.paid, datetime.now(UTC)
    db.flush()
    issue_payment_receipt(db, payment, inv, strict_receipt)
    record_income(db, payment, inv, user_id)
    db.flush()
    commissions.accrue(db, payment, inv)
    recompute_status(db, inv)


def refundable(db: Session, payment: Payment) -> Decimal:
    done = db.scalar(select(func.coalesce(func.sum(PaymentRefund.amount), 0)).where(PaymentRefund.payment_id == payment.id))
    return q2(payment.amount - done)


def create_refund(db: Session, payment: Payment, inv: Invoice, amount: Decimal, reason: str, user: CurrentUser | None,
                  provider_reason: int | None = None, strict_receipt: bool = True,
                  refund_method: PaymentMethod | None = None) -> PaymentRefund:
    """Qaytarish: chek (qaytarish), xarajat yozuvi, holat. Summa to'langanidan oshmaydi."""
    if payment.status != PaymentStatus.paid:
        raise HTTPException(409, "Faqat to'langan to'lovni qaytarish mumkin")
    if amount <= 0 or amount > refundable(db, payment):
        raise HTTPException(422, f"Qaytariladigan summa noto'g'ri (mumkin: {refundable(db, payment)})")
    alt = refund_method is not None and refund_method != payment.method   # boshqa usulda qaytarish (Click -> naqd/karta)
    refund = PaymentRefund(payment_id=payment.id, amount=amount, reason=reason, provider_reason=provider_reason,
                           refund_method=refund_method,
                           needs_provider_reconcile=alt and payment.method in (PaymentMethod.click, PaymentMethod.payme),
                           branch_id=payment.branch_id, created_by=user.id if user else None)
    db.add(refund)
    db.flush()
    lines = list(db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.position)))
    receipt = build_receipt(inv, lines, amount, refund_method or payment.method, "refund")
    refund.receipt_data = receipt
    try:
        result = fiscal.get_fiscal().refund(receipt, payment.receipt_id)
        refund.receipt_id, refund.receipt_status = result.receipt_id, ReceiptStatus.issued
        refund.receipt_data = {**receipt, "fiscal_sign": result.fiscal_sign, "qr_url": result.qr_url}
    except fiscal.FiscalError:
        if strict_receipt:
            raise
        refund.receipt_status = ReceiptStatus.failed
    db.add(Transaction(type=TransactionType.expense, amount=amount, category="Qaytarish", date=clinic_today(),
                       description=f"Qaytarish: hisob-faktura {inv.number} ({payment.method.value})", patient_id=inv.patient_id,
                       refund_id=refund.id, branch_id=payment.branch_id, created_by=user.id if user else None))
    db.flush()
    commissions.reverse(db, refund, payment)
    recompute_status(db, inv)
    return refund
