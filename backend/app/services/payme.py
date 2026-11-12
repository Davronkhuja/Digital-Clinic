# ruff: noqa: E501
"""Payme Merchant API (JSON-RPC 2.0, Payme -> biz). Ochiq hujjatga mos: autentifikatsiya `Authorization: Basic base64("Paycom:KEY")`,
summa tiyinda, vaqt millisekundda, tranzaksiya holatlari 1 (yaratilgan), 2 (bajarilgan), -1 (bajarilishidan oldin bekor),
-2 (bajarilgandan keyin bekor). Metodlar: CheckPerformTransaction, CreateTransaction, PerformTransaction, CancelTransaction,
CheckTransaction, GetStatement. Buyurtma (`account.order_id`) = bizdagi kutilayotgan `Payment` ID si.
Real kalit/merchant bo'lmagani uchun mock/test rejimida testlar bilan qurilgan; ishga tushirishdan oldin Payme sandbox bilan sinang.
Pul o'tkazish (so'm <-> tiyin) faqat `services/money.py`."""
import base64
import hmac
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Invoice, InvoiceLine, Payment
from app.schemas.enums import PaymentMethod, PaymentStatus
from app.services import payments
from app.services.money import q2, to_tiyin

TIMEOUT_MS = 12 * 60 * 60 * 1000  # yaratilgan tranzaksiya 12 soatdan keyin bajarib bo'lmaydi

# Xato kodlari (Payme hujjati)
ERR_AUTH = -32504
ERR_PARSE = -32700
ERR_REQUEST = -32600
ERR_METHOD = -32601
ERR_PARAMS = -32602
ERR_INTERNAL = -32400
ERR_AMOUNT = -31001
ERR_NOT_FOUND = -31003
ERR_CANT_CANCEL = -31007
ERR_CANT_PERFORM = -31008
ERR_ORDER_NOT_FOUND = -31050
ERR_ORDER_UNPAYABLE = -31051
ERR_ORDER_BUSY = -31099

MESSAGES = {
    ERR_AUTH: ("Недостаточно привилегий для выполнения метода", "Metodni bajarish uchun huquq yetarli emas", "Insufficient privilege to perform this method"),
    ERR_PARSE: ("Ошибка парсинга JSON", "JSON o'qishda xato", "JSON parse error"),
    ERR_REQUEST: ("Неверный запрос", "Noto'g'ri so'rov", "Invalid request"),
    ERR_METHOD: ("Метод не найден", "Metod topilmadi", "Method not found"),
    ERR_PARAMS: ("Неверные параметры", "Noto'g'ri parametrlar", "Invalid params"),
    ERR_INTERNAL: ("Системная ошибка", "Tizim xatosi", "System (internal) error"),
    ERR_AMOUNT: ("Неверная сумма", "Noto'g'ri summa", "Wrong amount"),
    ERR_NOT_FOUND: ("Транзакция не найдена", "Tranzaksiya topilmadi", "Transaction not found"),
    ERR_CANT_CANCEL: ("Невозможно отменить транзакцию", "Tranzaksiyani bekor qilib bo'lmaydi", "Unable to cancel transaction"),
    ERR_CANT_PERFORM: ("Невозможно выполнить операцию", "Operatsiyani bajarib bo'lmaydi", "Unable to perform operation"),
    ERR_ORDER_NOT_FOUND: ("Заказ не найден", "Buyurtma topilmadi", "Order not found"),
    ERR_ORDER_UNPAYABLE: ("Заказ не может быть оплачен", "Buyurtmani to'lab bo'lmaydi", "Order cannot be paid"),
    ERR_ORDER_BUSY: ("Заказ занят другой транзакцией", "Buyurtma boshqa tranzaksiya bilan band", "Order is busy with another transaction"),
}


class PaymeError(Exception):
    def __init__(self, code: int, data: str | None = None):
        self.code, self.data = code, data

    def body(self) -> dict:
        ru, uz, en = MESSAGES[self.code]
        return {"code": self.code, "message": {"ru": ru, "uz": uz, "en": en}, "data": self.data}


def now_ms() -> int:
    return int(time.time() * 1000)


def authorized(header: str | None) -> bool:
    """`Basic base64("Paycom:KEY")`; KEY rejimga qarab (test/prod). Bo'sh kalit: hech kim kira olmaydi. Doimiy vaqtda solishtirish."""
    expected = settings.payme_test_key if settings.payme_test_mode else settings.payme_key
    if not expected or not header or not header.startswith("Basic "):
        return False
    try:
        login, _, key = base64.b64decode(header[6:]).decode().partition(":")
    except Exception:
        return False
    return hmac.compare_digest(login, "Paycom") and hmac.compare_digest(key, expected)


def checkout_url(payment: Payment, lang: str = "uz") -> str | None:
    """Mijoz to'lov sahifasi: `m=<merchant>;ac.order_id=<payment id>;a=<tiyin>;l=<til>` base64. Sozlanmagan bo'lsa None."""
    if not settings.payme_merchant_id:
        return None
    base = "https://test.paycom.uz" if settings.payme_test_mode else "https://checkout.paycom.uz"
    params = f"m={settings.payme_merchant_id};ac.order_id={payment.id};a={to_tiyin(payment.amount)};l={lang}"
    return f"{base}/{base64.b64encode(params.encode()).decode()}"


def _account(params: dict) -> str:
    account = params.get("account")
    if not isinstance(account, dict) or not account.get("order_id"):
        raise PaymeError(ERR_ORDER_NOT_FOUND, "order_id")
    return str(account["order_id"])


def _amount(params: dict) -> int:
    amount = params.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise PaymeError(ERR_AMOUNT)
    return amount


def _load_order(db: Session, order_id: str, lock: bool = False) -> Payment:
    try:
        pid = uuid.UUID(order_id)
    except ValueError:
        raise PaymeError(ERR_ORDER_NOT_FOUND, "order_id")
    stmt = select(Payment).where(Payment.id == pid, Payment.method == PaymentMethod.payme)
    payment = db.scalar(stmt.with_for_update() if lock else stmt)
    if not payment:
        raise PaymeError(ERR_ORDER_NOT_FOUND, "order_id")
    return payment


def _by_txn(db: Session, txn_id) -> Payment:
    if not isinstance(txn_id, str) or not txn_id:
        raise PaymeError(ERR_PARAMS, "id")
    payment = db.scalar(select(Payment).where(Payment.method == PaymentMethod.payme, Payment.provider_txn_id == txn_id).with_for_update())
    if not payment:
        raise PaymeError(ERR_NOT_FOUND)
    return payment


def _data(p: Payment) -> dict:
    return dict(p.provider_data or {})


def receipt_detail(db: Session, payment: Payment) -> dict:
    """Fiskal chek tafsiloti (CheckPerformTransaction `detail`): qatorlar tiyinda, jami to'lov summasiga teng."""
    inv = db.get(Invoice, payment.invoice_id)
    lines = list(db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.position)))
    items = []
    for line, share in payments.allocate(lines, payment.amount):
        if share <= 0:
            continue
        tiyin = to_tiyin(share)
        whole = tiyin % line.quantity == 0
        vat = line.vat_percent
        items.append({"title": line.name, "price": tiyin // line.quantity if whole else tiyin, "count": line.quantity if whole else 1,
                      "code": line.mxik, "units": settings.payme_units_code, "package_code": line.package_code,
                      "vat_percent": int(vat) if vat == vat.to_integral_value() else float(vat)})
    return {"receipt_type": 0, "items": items}


def _expired(p: Payment) -> bool:
    return now_ms() - _data(p).get("create_time", 0) > TIMEOUT_MS


def _cancel_state(p: Payment, state: int, reason: int | None, at: int) -> None:
    data = _data(p)
    data.update(cancel_time=at, reason=reason)
    p.provider_data, p.provider_state = data, state
    if p.status == PaymentStatus.pending:
        p.status, p.cancelled_at = PaymentStatus.cancelled, datetime.now(UTC)


def check_perform(db: Session, params: dict) -> dict:
    payment = _load_order(db, _account(params))
    if _amount(params) != to_tiyin(payment.amount):
        raise PaymeError(ERR_AMOUNT)
    if payment.status != PaymentStatus.pending or payment.provider_state not in (None,):
        raise PaymeError(ERR_ORDER_UNPAYABLE, "order_id")
    return {"allow": True, "detail": receipt_detail(db, payment)}


def create_transaction(db: Session, params: dict) -> dict:
    txn_id = params.get("id")
    if not isinstance(txn_id, str) or not txn_id:
        raise PaymeError(ERR_PARAMS, "id")
    create_time = params.get("time")
    if isinstance(create_time, bool) or not isinstance(create_time, int):
        raise PaymeError(ERR_PARAMS, "time")
    existing = db.scalar(select(Payment).where(Payment.method == PaymentMethod.payme, Payment.provider_txn_id == txn_id).with_for_update())
    if existing:  # idempotent: shu tranzaksiya qayta kelsa
        if existing.provider_state != 1:
            raise PaymeError(ERR_CANT_PERFORM)
        if _expired(existing):
            _cancel_state(existing, -1, 4, now_ms())
            db.commit()
            raise PaymeError(ERR_CANT_PERFORM)
        return {"create_time": _data(existing)["create_time"], "transaction": str(existing.id), "state": 1}
    payment = _load_order(db, _account(params), lock=True)
    if _amount(params) != to_tiyin(payment.amount):
        raise PaymeError(ERR_AMOUNT)
    if payment.status != PaymentStatus.pending:
        raise PaymeError(ERR_ORDER_UNPAYABLE, "order_id")
    if payment.provider_txn_id and payment.provider_state == 1 and not _expired(payment):
        raise PaymeError(ERR_ORDER_BUSY, "order_id")      # buyurtmada boshqa faol tranzaksiya bor
    payment.provider_txn_id, payment.provider_state = txn_id, 1
    payment.provider_data = {"create_time": create_time, "perform_time": 0, "cancel_time": 0, "reason": None,
                             "account": {"order_id": str(payment.id)}}
    db.commit()
    return {"create_time": create_time, "transaction": str(payment.id), "state": 1}


def perform_transaction(db: Session, params: dict) -> dict:
    p = _by_txn(db, params.get("id"))
    data = _data(p)
    if p.provider_state == 2:
        return {"transaction": str(p.id), "perform_time": data["perform_time"], "state": 2}
    if p.provider_state != 1:
        raise PaymeError(ERR_CANT_PERFORM)
    if _expired(p):
        _cancel_state(p, -1, 4, now_ms())
        db.commit()
        raise PaymeError(ERR_CANT_PERFORM)
    at = now_ms()
    data["perform_time"] = at
    p.provider_data, p.provider_state = data, 2
    # pul olindi: chek keyinroq qayta berilishi mumkin (strict=False), daromad yoziladi
    payments.mark_paid(db, p, db.get(Invoice, p.invoice_id), None, strict_receipt=False)
    db.commit()
    return {"transaction": str(p.id), "perform_time": at, "state": 2}


def cancel_transaction(db: Session, params: dict) -> dict:
    p = _by_txn(db, params.get("id"))
    reason = params.get("reason")
    if reason is not None and (isinstance(reason, bool) or not isinstance(reason, int)):
        raise PaymeError(ERR_PARAMS, "reason")
    data = _data(p)
    if p.provider_state in (-1, -2):
        return {"transaction": str(p.id), "cancel_time": data.get("cancel_time", 0), "state": p.provider_state}
    at = now_ms()
    if p.provider_state == 1:
        _cancel_state(p, -1, reason, at)
    elif p.provider_state == 2:
        if payments.refundable(db, p) != q2(p.amount):
            raise PaymeError(ERR_CANT_CANCEL)           # qisman qaytarilgan: Payme bekor qilishi mumkin emas
        payments.create_refund(db, p, db.get(Invoice, p.invoice_id), q2(p.amount), f"Payme bekor qildi (sabab {reason})", None,
                               provider_reason=reason, strict_receipt=False)
        _cancel_state(p, -2, reason, at)
    else:
        raise PaymeError(ERR_CANT_CANCEL)
    db.commit()
    return {"transaction": str(p.id), "cancel_time": at, "state": p.provider_state}


def check_transaction(db: Session, params: dict) -> dict:
    p = _by_txn(db, params.get("id"))
    d = _data(p)
    return {"create_time": d.get("create_time", 0), "perform_time": d.get("perform_time", 0), "cancel_time": d.get("cancel_time", 0),
            "transaction": str(p.id), "state": p.provider_state, "reason": d.get("reason")}


def get_statement(db: Session, params: dict) -> dict:
    start, end = params.get("from"), params.get("to")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (start, end)):
        raise PaymeError(ERR_PARAMS)
    rows = db.scalars(select(Payment).where(Payment.method == PaymentMethod.payme, Payment.provider_txn_id.is_not(None))
                      .order_by(Payment.created_at))
    out = []
    for p in rows:
        d = _data(p)
        if start <= d.get("create_time", 0) <= end:
            out.append({"id": p.provider_txn_id, "time": d["create_time"], "amount": to_tiyin(p.amount), "account": {"order_id": str(p.id)},
                        "create_time": d["create_time"], "perform_time": d.get("perform_time", 0), "cancel_time": d.get("cancel_time", 0),
                        "transaction": str(p.id), "state": p.provider_state, "reason": d.get("reason")})
    return {"transactions": out}


METHODS = {"CheckPerformTransaction": check_perform, "CreateTransaction": create_transaction, "PerformTransaction": perform_transaction,
           "CancelTransaction": cancel_transaction, "CheckTransaction": check_transaction, "GetStatement": get_statement}


def handle(db: Session, payload) -> dict:
    """Bitta JSON-RPC so'rovi -> javob lug'ati (har doim HTTP 200; xato `error` ichida)."""
    rpc_id = payload.get("id") if isinstance(payload, dict) else None
    try:
        if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0" or not isinstance(payload.get("method"), str):
            raise PaymeError(ERR_REQUEST)
        method = METHODS.get(payload["method"])
        if not method:
            raise PaymeError(ERR_METHOD)
        params = payload.get("params")
        if not isinstance(params, dict):
            raise PaymeError(ERR_PARAMS)
        return {"jsonrpc": "2.0", "id": rpc_id, "result": method(db, params)}
    except PaymeError as exc:
        db.rollback()
        return {"jsonrpc": "2.0", "id": rpc_id, "error": exc.body()}
    except Exception:
        db.rollback()
        return {"jsonrpc": "2.0", "id": rpc_id, "error": PaymeError(ERR_INTERNAL).body()}


