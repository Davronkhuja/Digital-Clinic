# ruff: noqa: E501
"""Kassa smenasi hisobi: naqd/karta to'lovlari va qaytarishlar (smenaga bog'langan), kutilgan naqd, onlayn to'lovlar (ma'lumot uchun)."""
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CashMovement, CashShift, Payment, PaymentRefund, Staff, User
from app.schemas.enums import CashMovementKind, CashShiftStatus, PaymentMethod, PaymentStatus, ReceiptStatus
from app.services.money import q2


def open_shift_of(db: Session, user_id: uuid.UUID) -> CashShift | None:
    return db.scalar(select(CashShift).where(CashShift.opened_by == user_id, CashShift.status == CashShiftStatus.open))


def require_open_shift(db: Session, user_id: uuid.UUID) -> CashShift:
    shift = open_shift_of(db, user_id)
    if not shift:
        raise HTTPException(409, "Kassa smenasi ochilmagan: avval smenani oching")
    return shift


def cashier_name(db: Session, user_id: uuid.UUID | None) -> str | None:
    if not user_id:
        return None
    return db.scalar(select(Staff.full_name).join(User, User.staff_id == Staff.id).where(User.id == user_id))


def _sum(db: Session, column, *conditions) -> tuple[Decimal, int]:
    total, count = db.execute(select(func.coalesce(func.sum(column), 0), func.count()).where(*conditions)).one()
    return q2(total), count


def report(db: Session, shift: CashShift) -> dict:
    """X (ochiq smena, joriy) yoki Z (yopilgan, qotgan) hisobot raqamlari. Hammasi bazadan."""
    until = shift.closed_at or datetime.now(UTC)
    block: dict[str, dict] = {}
    for method in (PaymentMethod.cash, PaymentMethod.card):
        paid, n_paid = _sum(db, Payment.amount, Payment.shift_id == shift.id, Payment.status == PaymentStatus.paid, Payment.method == method)
        refunded, n_ref = _sum(db, PaymentRefund.amount, PaymentRefund.shift_id == shift.id, PaymentRefund.refund_method == method)
        block[method.value.lower()] = {"payments_count": n_paid, "payments_total": paid, "refunds_count": n_ref, "refunds_total": refunded,
                                       "net": paid - refunded}
    online = {}
    for method in (PaymentMethod.click, PaymentMethod.payme):
        total, n = _sum(db, Payment.amount, Payment.method == method, Payment.status == PaymentStatus.paid, Payment.branch_id == shift.branch_id,
                        Payment.paid_at >= shift.opened_at, Payment.paid_at <= until)
        online[method.value.lower()] = {"payments_count": n, "payments_total": total}
    missing = db.scalar(select(func.count()).select_from(Payment).where(
        Payment.shift_id == shift.id, Payment.status == PaymentStatus.paid, Payment.receipt_status != ReceiptStatus.issued))
    cash, card = block["cash"], block["card"]
    moves = {}
    for kind in (CashMovementKind.withdrawal, CashMovementKind.payout):
        total, n = _sum(db, CashMovement.amount, CashMovement.shift_id == shift.id, CashMovement.kind == kind)
        moves[kind.value] = {"count": n, "total": total}
    expected = q2(shift.opening_cash + cash["net"] - moves["Withdrawal"]["total"] - moves["Payout"]["total"])
    return {
        "shift_id": str(shift.id), "z_number": shift.z_number, "status": shift.status, "cashier": cashier_name(db, shift.opened_by),
        "opened_at": shift.opened_at, "closed_at": shift.closed_at, "opening_cash": shift.opening_cash, "cash": cash, "card": card,
        "online": online, "withdrawals": moves["Withdrawal"], "payouts": moves["Payout"], "sales_total": cash["payments_total"] + card["payments_total"],
        "refunds_total": cash["refunds_total"] + card["refunds_total"], "net_total": cash["net"] + card["net"],
        "expected_cash": expected, "counted_cash": shift.counted_cash, "difference": shift.difference, "receipts_missing": missing or 0,
    }


def current_cash(db: Session, shift: CashShift) -> Decimal:
    """Kassadagi hozirgi kutilgan naqd (chiqim summasi undan oshmasligi uchun)."""
    return report(db, shift)["expected_cash"]
