# ruff: noqa: E501
"""OTP (SMS kod) va tezlik cheklovi. Kod 6 raqam, xeshlanadi (kalit bilan), 5 daqiqa, 5 urinish; telefon uchun 15 daqiqada 3 ta so'rov,
IP uchun soatiga 10 ta. Tasdiqlangach qisqa muddatli imzolangan `verification token` beriladi (telefon egaligini isbotlaydi)."""
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ClinicSettings, OtpCode, RateEvent
from app.schemas.enums import Channel
from app.services import links, messaging
from app.services.audit import client_ip

CODE_TTL = timedelta(minutes=5)
MAX_ATTEMPTS = 5
PHONE_LIMIT = (3, timedelta(minutes=15))
IP_LIMIT = (10, timedelta(hours=1))
VERIFIED_TTL = timedelta(minutes=30)
PURPOSES = ("booking", "portal", "telegram")


def _hash(phone: str, code: str) -> str:
    return hmac.new((settings.link_secret or settings.jwt_secret).encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def rate_check(db: Session, key: str, action: str, limit: int, window: timedelta, record: bool = True) -> None:
    """`window` ichida `limit` ta hodisa bo'lsa 429. Hodisa yoziladi."""
    since = datetime.now(UTC) - window
    count = db.scalar(select(func.count()).select_from(RateEvent).where(RateEvent.action == action, RateEvent.key == key, RateEvent.created_at >= since))
    if count >= limit:
        raise HTTPException(429, "So'rovlar juda ko'p. Birozdan keyin qayta urinib ko'ring")
    if record:
        db.add(RateEvent(key=key, action=action))


def request_ip(request: Request) -> str:
    return (client_ip(request) or "unknown")[:45]


def send_code(db: Session, ip: str, phone: str, purpose: str, branch_id, language: str = "uz") -> None:
    rate_check(db, ip, "otp_ip", *IP_LIMIT)
    rate_check(db, phone, "otp_phone", *PHONE_LIMIT)
    code = f"{secrets.randbelow(900000) + 100000}"
    db.add(OtpCode(phone=phone, purpose=purpose, code_hash=_hash(phone, code), expires_at=datetime.now(UTC) + CODE_TTL, ip=ip))
    row = db.scalar(select(ClinicSettings).where(ClinicSettings.branch_id == branch_id))
    body = messaging.render(db, "otp", language, clinic=row.clinic_name if row else "Klinika", code=code)
    messaging.enqueue(db, branch_id=branch_id, kind="otp", body=body, patient=None, channel=Channel.sms, to_address=phone, language=language)
    db.commit()
    # OTP darhol yuboriladi (navbat Celery'ni kutmasin)
    messaging.dispatch_due(db)


def verify_code(db: Session, phone: str, purpose: str, code: str) -> str:
    """To'g'ri bo'lsa imzolangan tasdiqlash tokenini qaytaradi. Noto'g'ri urinish hisoblanadi; limit oshsa kod bekor."""
    otp = db.scalar(select(OtpCode).where(OtpCode.phone == phone, OtpCode.purpose == purpose, OtpCode.verified_at.is_(None),
                                          OtpCode.expires_at > datetime.now(UTC)).order_by(OtpCode.created_at.desc()).with_for_update())
    if not otp or otp.attempts >= MAX_ATTEMPTS:
        raise HTTPException(400, "Kod yaroqsiz yoki muddati tugagan: yangi kod so'rang")
    otp.attempts += 1
    if not hmac.compare_digest(otp.code_hash, _hash(phone, code.strip())):
        db.commit()
        raise HTTPException(400, "Kod noto'g'ri")
    otp.verified_at = datetime.now(UTC)
    db.commit()
    return links.make_token("otpv", {"phone": phone, "purpose": purpose}, datetime.now(UTC) + VERIFIED_TTL)


def read_verified(token: str, purpose: str) -> str:
    data = links.read_token(token, "otpv")
    if not data or data.get("purpose") != purpose:
        raise HTTPException(401, "Telefon tasdiqlanmagan yoki muddati tugagan")
    return data["phone"]
