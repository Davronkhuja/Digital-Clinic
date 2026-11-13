# ruff: noqa: E501
"""Xabarlar: kanal adapterlari (SMS, Telegram), rozilik, tungi vaqt, navbat va yuborish (qayta urinish bilan), xabar logi.

Qoidalar: rozilik bo'lmasa xabar yuborilmaydi (navbatga qo'yishda va YUBORISH paytida ham tekshiriladi); tungi vaqtda
(standart 21:00-08:00 Asia/Tashkent) eslatmalar ertalabga qoldiriladi; OTP tranzaksion: rozilik va tungi cheklov yo'q.
Yuborilmagan xabar ham logga `Skipped` + sabab bilan yoziladi (hisobot uchun)."""
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Message, MessageTemplate, Patient, PatientConsent, TelegramLink
from app.schemas.enums import Channel, ConsentStatus, MessageStatus
from app.services import app_settings
from app.services.message_defaults import DEFAULTS
from app.services.periods import CLINIC_TZ
from app.services.phone import normalize_phone

log = logging.getLogger(__name__)
TRANSACTIONAL = {"otp"}  # rozilik va tungi cheklovsiz (foydalanuvchi o'zi so'ragan tasdiqlash kodi)
MAX_ATTEMPTS = 3
BACKOFF_MINUTES = (5, 15, 60)


class SendError(Exception):
    """Yuborib bo'lmadi (provayder xatosi): qayta uriniladi."""


@dataclass
class SendResult:
    provider_message_id: str


class ChannelAdapter(Protocol):
    def send(self, to: str, text: str) -> SendResult: ...


class MockSmsAdapter:
    """Test/demo: tashqi so'rovsiz. `SENT` ro'yxatida saqlanadi (testlar tekshiradi)."""

    SENT: list[tuple[str, str]] = []

    def send(self, to: str, text: str) -> SendResult:
        self.SENT.append((to, text))
        return SendResult(f"MOCKSMS-{uuid.uuid4().hex[:10]}")


class MockTelegramAdapter:
    SENT: list[tuple[str, str]] = []

    def send(self, to: str, text: str) -> SendResult:
        self.SENT.append((to, text))
        return SendResult(f"MOCKTG-{uuid.uuid4().hex[:10]}")


class TelegramBotAdapter:
    """Telegram Bot API (`sendMessage`). Token faqat .env da."""

    def send(self, to: str, text: str) -> SendResult:
        try:
            res = httpx.post(f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                             json={"chat_id": to, "text": text}, timeout=15)
            res.raise_for_status()
            return SendResult(str(res.json()["result"]["message_id"]))
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise SendError(f"Telegram: {exc.__class__.__name__}") from exc


_adapters: dict[Channel, ChannelAdapter] = {}


def get_adapter(channel: Channel) -> ChannelAdapter:
    if channel not in _adapters:
        if channel == Channel.sms:
            if settings.sms_backend != "mock":
                raise RuntimeError(f"Noma'lum SMS_BACKEND: {settings.sms_backend} (hozircha faqat mock; mahalliy provayder adapteri hujjat va kalit bilan)")
            _adapters[channel] = MockSmsAdapter()
        else:
            _adapters[channel] = TelegramBotAdapter() if settings.telegram_bot_token else MockTelegramAdapter()
    return _adapters[channel]


_GSM7 = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà")


def sms_segments(text: str) -> int:
    """SMS qismlari soni: GSM-7 (lotin) 160/153, aks holda UCS-2 (kirill, ʻ) 70/67."""
    if not text:
        return 0
    single, multi = (160, 153) if all(ch in _GSM7 for ch in text) else (70, 67)
    return 1 if len(text) <= single else -(-len(text) // multi)


# ---------- shablon va rozilik ----------

class _Safe(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render(db: Session, key: str, language: str, **values) -> str:
    """Sozlamalardagi faol shablon, bo'lmasa standart; o'sha tilda yo'q bo'lsa o'zbekcha."""
    row = db.scalar(select(MessageTemplate).where(MessageTemplate.key == key, MessageTemplate.language == language,
                                                   MessageTemplate.is_active.is_(True)))
    body = row.body if row else DEFAULTS.get((key, language)) or DEFAULTS[(key, "uz")]
    return body.format_map(_Safe(values))


def has_consent(db: Session, patient_id: uuid.UUID, channel: Channel) -> bool:
    status = db.scalar(select(PatientConsent.status).where(PatientConsent.patient_id == patient_id, PatientConsent.channel == channel))
    return status == ConsentStatus.granted


def telegram_chat(db: Session, patient_id: uuid.UUID) -> str | None:
    return db.scalar(select(TelegramLink.chat_id).where(TelegramLink.patient_id == patient_id, TelegramLink.verified_at.is_not(None)))


def pick_channel(db: Session, patient: Patient) -> tuple[Channel, str] | None:
    """Rozilik bor kanal: Telegram (ulangan bo'lsa, arzon) keyin SMS. Rozilik yoki aloqa bo'lmasa None."""
    chat = telegram_chat(db, patient.id)
    if chat and has_consent(db, patient.id, Channel.telegram):
        return Channel.telegram, chat
    phone = normalize_phone(patient.phone)
    if phone and has_consent(db, patient.id, Channel.sms):
        return Channel.sms, phone
    return None


def quiet_adjust(db: Session, branch_id: uuid.UUID, when: datetime) -> datetime:
    """Tungi vaqtga (klinika vaqti, standart 21:00-08:00) tushsa, ertalabki chegaraga suradi."""
    row = app_settings.clinic_row(db, branch_id)
    start_h, end_h = (row.quiet_start_hour, row.quiet_end_hour) if row else (21, 8)
    local = when.astimezone(CLINIC_TZ)
    if start_h > end_h:  # tun yarmidan o'tadi
        in_quiet = local.hour >= start_h or local.hour < end_h
    else:
        in_quiet = start_h <= local.hour < end_h
    if not in_quiet:
        return when
    morning = local.replace(hour=end_h, minute=0, second=0, microsecond=0)
    if local.hour >= start_h and start_h > end_h:
        morning += timedelta(days=1)
    elif morning <= local:
        morning += timedelta(days=1)
    return morning.astimezone(UTC)


def enqueue(db: Session, *, branch_id: uuid.UUID, kind: str, body: str, patient: Patient | None, channel: Channel | None = None,
            to_address: str | None = None, scheduled_at: datetime | None = None, appointment_id: uuid.UUID | None = None,
            dedupe_key: str | None = None, language: str = "uz", created_by: uuid.UUID | None = None) -> Message | None:
    """Xabarni navbatga qo'yadi. `None` qaytsa: dedupe (allaqachon bor). Rozilik/aloqa yo'q bo'lsa `Skipped` yoziladi (hisobot uchun).
    Tranzaksion (OTP): kanal/manzil aniq beriladi, rozilik va tungi cheklov yo'q."""
    if dedupe_key and db.scalar(select(Message.id).where(Message.dedupe_key == dedupe_key)):
        return None
    now = datetime.now(UTC)
    when = scheduled_at or now
    skip = None
    if kind in TRANSACTIONAL:
        if not channel or not to_address:
            raise ValueError("Tranzaksion xabar uchun kanal va manzil kerak")
    else:
        if patient is None:
            raise ValueError("Bemor kerak")
        picked = pick_channel(db, patient) if channel is None else ((channel, to_address) if has_consent(db, patient.id, channel) and to_address else None)
        if picked:
            channel, to_address = picked
            when = quiet_adjust(db, branch_id, when)
        else:
            skip = "rozilik yoki aloqa yo'q"
            channel, to_address = channel or Channel.sms, to_address or (normalize_phone(patient.phone) or "")
    msg = Message(patient_id=patient.id if patient else None, channel=channel, to_address=to_address or "", kind=kind, language=language,
                  body=body, status=MessageStatus.skipped if skip else MessageStatus.queued, scheduled_at=when, skip_reason=skip,
                  appointment_id=appointment_id, dedupe_key=dedupe_key, branch_id=branch_id, created_by=created_by)
    db.add(msg)
    db.flush()
    return msg


def _skip(msg: Message, reason: str) -> None:
    msg.status, msg.skip_reason = MessageStatus.skipped, reason


def deliver(db: Session, msg: Message, now: datetime) -> None:
    """Bitta navbatdagi xabarni yuboradi. Rozilik/qabul holati/tungi vaqt yuborish paytida qayta tekshiriladi."""
    if msg.kind not in TRANSACTIONAL:
        if msg.patient_id and not has_consent(db, msg.patient_id, msg.channel):
            return _skip(msg, "rozilik bekor qilingan")
        adjusted = quiet_adjust(db, msg.branch_id, now)
        if adjusted > now:
            msg.scheduled_at = adjusted
            return
    if msg.appointment_id and msg.kind.startswith("reminder"):
        from app.models import Appointment
        from app.schemas.enums import AppointmentStatus

        appt = db.get(Appointment, msg.appointment_id)
        if not appt or appt.status != AppointmentStatus.scheduled or appt.starts_at <= now:
            return _skip(msg, "qabul faol emas yoki boshlangan")
    msg.attempts += 1
    try:
        result = get_adapter(msg.channel).send(msg.to_address, msg.body)
    except SendError as exc:
        msg.last_error = str(exc)[:300]
        if msg.attempts >= MAX_ATTEMPTS:
            msg.status = MessageStatus.failed
        else:
            msg.scheduled_at = now + timedelta(minutes=BACKOFF_MINUTES[min(msg.attempts - 1, len(BACKOFF_MINUTES) - 1)])
        return
    msg.status, msg.sent_at, msg.provider_message_id, msg.last_error = MessageStatus.sent, now, result.provider_message_id, None
    msg.sms_segments = sms_segments(msg.body) if msg.channel == Channel.sms else 0


def dispatch_due(db: Session, now: datetime | None = None, limit: int = 200) -> dict[str, int]:
    """Muddati kelgan navbatdagi xabarlarni yuboradi (Celery beat har daqiqada). Parallel ishchilar `SKIP LOCKED` bilan bo'linadi."""
    now = now or datetime.now(UTC)
    rows = db.scalars(select(Message).where(Message.status == MessageStatus.queued, Message.scheduled_at <= now)
                      .order_by(Message.scheduled_at).limit(limit).with_for_update(skip_locked=True)).all()
    stats = {"sent": 0, "failed": 0, "skipped": 0, "retry": 0, "deferred": 0}
    for msg in rows:
        before = msg.scheduled_at
        deliver(db, msg, now)
        key = {MessageStatus.sent: "sent", MessageStatus.failed: "failed", MessageStatus.skipped: "skipped"}.get(msg.status)
        stats[key or ("retry" if msg.attempts and msg.scheduled_at != before else "deferred")] += 1
    db.commit()
    return stats
