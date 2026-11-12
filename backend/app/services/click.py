"""Click SHOP API (Prepare/Complete, Click -> biz). Imzo: md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id
[+ merchant_prepare_id (Complete)] + amount + action + sign_time). Xato kodlari: 0 muvaffaqiyat, -1 imzo xato, -2 summa xato,
-3 action yo'q, -4 allaqachon to'langan, -5 buyurtma yo'q, -6 tranzaksiya yo'q, -7 yangilab bo'lmadi, -8 so'rov xato, -9 bekor qilingan.
`merchant_trans_id` = bizdagi kutilayotgan `Payment` ID si. Pul so'm <-> tiyin faqat `services/money.py`.
Real kalit yo'q: mock/test bilan qurilgan; ishga tushirishdan oldin Click sandbox'da sinash shart."""
import hashlib
import hmac
import logging
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Invoice, Payment
from app.schemas.enums import PaymentMethod, PaymentStatus
from app.services import payments
from app.services.money import format_sum, to_tiyin

log = logging.getLogger(__name__)
OK, E_SIGN, E_AMOUNT, E_ACTION, E_PAID, E_ORDER, E_TXN, E_UPDATE, E_REQUEST, E_CANCELLED = 0, -1, -2, -3, -4, -5, -6, -7, -8, -9
NOTES = {
    OK: "Success", E_SIGN: "SIGN CHECK FAILED!", E_AMOUNT: "Incorrect parameter amount", E_ACTION: "Action not found",
    E_PAID: "Already paid", E_ORDER: "Order does not exist", E_TXN: "Transaction does not exist",
    E_UPDATE: "Failed to update order", E_REQUEST: "Error in request from click", E_CANCELLED: "Transaction cancelled",
}
STATE_PREPARED, STATE_COMPLETED, STATE_CANCELLED = 1, 2, -1


def secret() -> str:
    return settings.click_test_secret_key if settings.click_test_mode else settings.click_secret_key


def sign(p: dict, complete: bool) -> str:
    parts = [p.get("click_trans_id", ""), p.get("service_id", ""), secret(), p.get("merchant_trans_id", "")]
    if complete:
        parts.append(p.get("merchant_prepare_id", ""))
    parts += [p.get("amount", ""), p.get("action", ""), p.get("sign_time", "")]
    return hashlib.md5("".join(str(x) for x in parts).encode()).hexdigest()


def valid_sign(p: dict, complete: bool) -> bool:
    """Maxfiy kalit bo'sh bo'lsa hech qachon to'g'ri emas (bo'sh kalit bilan imzoni soxtalashtirish mumkin bo'lmasligi uchun)."""
    given = str(p.get("sign_string", "")).lower()
    return bool(secret()) and hmac.compare_digest(given, sign(p, complete))


def checkout_url(payment: Payment) -> str | None:
    if not settings.click_service_id or not settings.click_merchant_id:
        return None
    return (f"https://my.click.uz/services/pay?service_id={settings.click_service_id}&merchant_id={settings.click_merchant_id}"
            f"&amount={format_sum(payment.amount)}&transaction_param={payment.id}")


def _reply(p: dict, error: int, **extra) -> dict:
    out = {"click_trans_id": p.get("click_trans_id"), "merchant_trans_id": p.get("merchant_trans_id"), **extra,
           "error": error, "error_note": NOTES[error]}
    return out


def _amount_matches(raw, payment: Payment) -> bool:
    try:
        return to_tiyin(Decimal(str(raw))) == to_tiyin(payment.amount)
    except (InvalidOperation, ValueError):
        return False


def _load(db: Session, order_id: str) -> Payment | None:
    try:
        pid = uuid.UUID(str(order_id))
    except ValueError:
        return None
    return db.scalar(select(Payment).where(Payment.id == pid, Payment.method == PaymentMethod.click).with_for_update())


def _cancel(p: Payment) -> None:
    data = dict(p.provider_data or {})
    data["cancel_time"] = int(time.time() * 1000)
    p.provider_data, p.provider_state = data, STATE_CANCELLED
    if p.status == PaymentStatus.pending:
        p.status, p.cancelled_at = PaymentStatus.cancelled, datetime.now(UTC)


def _int(value) -> int | None:
    try:
        return int(str(value))
    except ValueError:
        return None


def prepare(db: Session, p: dict) -> dict:
    payment = _load(db, p.get("merchant_trans_id", ""))
    if not payment:
        return _reply(p, E_ORDER)
    if not _amount_matches(p.get("amount"), payment):
        return _reply(p, E_AMOUNT)
    if payment.status == PaymentStatus.paid:
        return _reply(p, E_PAID)
    if payment.status == PaymentStatus.cancelled:
        return _reply(p, E_CANCELLED)
    click_id = str(p.get("click_trans_id", ""))
    if payment.provider_state == STATE_PREPARED:
        if payment.provider_txn_id == click_id:  # idempotent: shu Prepare qayta keldi
            return _reply(p, OK, merchant_prepare_id=str(payment.id))
        return _reply(p, E_REQUEST)              # buyurtma boshqa Click tranzaksiyasi bilan band
    if (_int(p.get("error")) or 0) < 0:          # Click o'z tomonida to'lovni rad etdi
        _cancel(payment)
        db.commit()
        return _reply(p, E_CANCELLED)
    if db.scalar(select(Payment.id).where(Payment.method == PaymentMethod.click, Payment.provider_txn_id == click_id)):
        return _reply(p, E_REQUEST)              # click_trans_id boshqa buyurtmada ishlatilgan
    payment.provider_txn_id, payment.provider_state = click_id, STATE_PREPARED
    payment.provider_data = {"click_paydoc_id": str(p.get("click_paydoc_id", "")), "prepare_time": int(time.time() * 1000),
                             "complete_time": 0, "cancel_time": 0}
    db.commit()
    return _reply(p, OK, merchant_prepare_id=str(payment.id))


def complete(db: Session, p: dict) -> dict:
    payment = _load(db, p.get("merchant_trans_id", ""))
    if not payment:
        return _reply(p, E_ORDER)
    if payment.status == PaymentStatus.paid and payment.provider_state == STATE_COMPLETED:
        return _reply(p, E_PAID)
    if payment.provider_state != STATE_PREPARED or payment.provider_txn_id != str(p.get("click_trans_id", "")) \
            or str(p.get("merchant_prepare_id", "")) != str(payment.id):
        return _reply(p, E_CANCELLED if payment.status == PaymentStatus.cancelled else E_TXN)
    if not _amount_matches(p.get("amount"), payment):
        return _reply(p, E_AMOUNT)
    if (_int(p.get("error")) or 0) < 0:          # Click to'lovni bajarmadi: bekor
        _cancel(payment)
        db.commit()
        return _reply(p, E_CANCELLED)
    data = dict(payment.provider_data or {})
    data["complete_time"] = int(time.time() * 1000)
    payment.provider_data, payment.provider_state = data, STATE_COMPLETED
    payments.mark_paid(db, payment, db.get(Invoice, payment.invoice_id), None, strict_receipt=False)
    db.commit()
    return _reply(p, OK, merchant_confirm_id=str(payment.id))


def handle(db: Session, p: dict) -> dict:
    """Bitta so'rov -> javob (HTTP 200). Tartib: imzo -> service_id -> action."""
    action = _int(p.get("action"))
    try:
        if action not in (0, 1):
            return _reply(p, E_ACTION) if valid_sign(p, complete=action == 1) else _reply(p, E_SIGN)
        if not valid_sign(p, complete=action == 1):
            return _reply(p, E_SIGN)
        if str(p.get("service_id", "")) != settings.click_service_id or not settings.click_service_id:
            return _reply(p, E_REQUEST)
        return prepare(db, p) if action == 0 else complete(db, p)
    except Exception:
        log.exception("Click so'rovini qayta ishlashda xato")
        db.rollback()
        return _reply(p, E_UPDATE)
