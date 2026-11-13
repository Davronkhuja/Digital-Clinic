"""Login talab qilmaydigan imzolangan, muddatli havolalar (qabulni tasdiqlash/bekor qilish, bo'sh vaqtni band qilish).
Token: `itsdangerous` emas, HMAC-SHA256 bilan o'z formatimiz (qo'shimcha kutubxonasiz): payload JSON + imzo, `exp` (UTC) muddati."""
import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime

from app.core.config import settings


def _key() -> bytes:
    return (settings.link_secret or settings.jwt_secret).encode()


def make_token(purpose: str, data: dict, expires_at: datetime) -> str:
    payload = {"p": purpose, "d": data, "e": int(expires_at.timestamp())}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
    sig = base64.urlsafe_b64encode(hmac.new(_key(), body, hashlib.sha256).digest()).rstrip(b"=")
    return f"{body.decode()}.{sig.decode()}"


def read_token(token: str, purpose: str) -> dict | None:
    """Imzo, maqsad va muddat to'g'ri bo'lsa ma'lumot, aks holda None."""
    try:
        body, sig = token.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(_key(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
    if payload.get("p") != purpose or payload.get("e", 0) < time.time():
        return None
    return payload["d"]


def appointment_link(appointment_id: uuid.UUID, starts_at: datetime) -> str:
    """Tasdiqlash/bekor qilish havolasi: qabul boshlanguncha amal qiladi."""
    return f"{settings.public_base_url}/p/a/{make_token('appt', {'id': str(appointment_id)}, starts_at)}"
