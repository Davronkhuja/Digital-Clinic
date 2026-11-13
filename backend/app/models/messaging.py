# ruff: noqa: E501
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import Channel, ConsentStatus, MessageStatus


class PatientConsent(BaseModel):
    """Bemorning kanal bo'yicha roziligi (SMS, Telegram). Rozilik bo'lmasa xabar yuborilmaydi (yuborish paytida ham tekshiriladi).
    Voz kechish: `Revoked`. Tarix auditda (kim, qachon, qayerdan)."""

    __tablename__ = "patient_consents"
    __table_args__ = (UniqueConstraint("patient_id", "channel"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    channel: Mapped[Channel] = mapped_column(enum_col(Channel, "channel", 8))
    status: Mapped[ConsentStatus] = mapped_column(enum_col(ConsentStatus, "status", 7))
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(20))  # staff, online, portal, bot, link
    note: Mapped[str | None] = mapped_column(String(300))


class MessageTemplate(BaseModel):
    """Xabar shabloni (o'zbek lotin / rus), Sozlamalarda tahrirlanadi. Joy egalari: {patient}, {doctor}, {date}, {time}, {clinic}, {link}, {code}..."""

    __tablename__ = "message_templates"
    __table_args__ = (UniqueConstraint("key", "language"),)

    key: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(2))  # uz, ru
    body: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Message(BranchScoped, BaseModel):
    """Chiquvchi xabar logi: navbat, holat, qayta urinishlar, SMS soni (xarajat). O'chirilmaydi."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("uq_messages_dedupe", "dedupe_key", unique=True, postgresql_where=text("dedupe_key IS NOT NULL")),
        Index("ix_messages_due", "status", "scheduled_at"),
    )

    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    channel: Mapped[Channel] = mapped_column(enum_col(Channel, "channel", 8))
    to_address: Mapped[str] = mapped_column(String(60))  # telefon (+998...) yoki Telegram chat_id
    kind: Mapped[str] = mapped_column(String(40), index=True)  # reminder_24h, reminder_2h, otp, recall, waitlist_offer, ...
    language: Mapped[str] = mapped_column(String(2), default="uz")
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[MessageStatus] = mapped_column(enum_col(MessageStatus, "status", 7), default=MessageStatus.queued)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(300))
    provider_message_id: Mapped[str | None] = mapped_column(String(100))
    sms_segments: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # SMS qismlari soni (xarajat hisobi)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"), index=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(120))
    skip_reason: Mapped[str | None] = mapped_column(String(120))


class TelegramLink(BaseModel):
    """Bemorning Telegram'ga ulanishi: chat_id telefon tasdiqlangandan (kontakt + OTP) keyin `verified_at`. Tibbiy natijalar faqat shundan keyin."""

    __tablename__ = "telegram_links"
    __table_args__ = (UniqueConstraint("chat_id", "patient_id"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    chat_id: Mapped[str] = mapped_column(String(30), index=True)
    phone: Mapped[str] = mapped_column(String(20))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OtpCode(BaseModel):
    """Bir martalik SMS kod (telefonni tasdiqlash). Kod xeshlanadi, 5 daqiqa amal qiladi, 5 urinish."""

    __tablename__ = "otp_codes"

    phone: Mapped[str] = mapped_column(String(20), index=True)
    purpose: Mapped[str] = mapped_column(String(20))  # booking, portal, telegram
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(45))


class RateEvent(BaseModel):
    """Ochiq endpointlar uchun tezlik cheklovi: kalit (IP yoki telefon) + amal + vaqt (DB asosida: qayta ishga tushganda yo'qolmaydi)."""

    __tablename__ = "rate_events"
    __table_args__ = (Index("ix_rate_events_lookup", "action", "key", "created_at"),)

    key: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(30))
