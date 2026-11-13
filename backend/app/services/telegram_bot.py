# ruff: noqa: E501
"""Telegram bot mantig'i (transportdan mustaqil: aiogram faqat `app/bot.py` da). Telefonni ulash: Telegram kontakt (faqat o'z kontakti) + SMS OTP.
Tibbiy natijalar FAQAT telefon tasdiqlangandan keyin (`verified_at`). Eslatmalar va tasdiqlash/bekor qilish; rozilik va voz kechish aniq buyruqlar bilan."""
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Appointment, Branch, LabOrder, Patient, Staff, TelegramLink
from app.schemas.enums import AppointmentStatus, Channel, LabOrderStatus, StatusEnum
from app.services import otp
from app.services.periods import CLINIC_TZ
from app.services.phone import normalize_phone

CONTACT_BUTTON = "📱 Telefonni ulash"


@dataclass
class Reply:
    text: str
    buttons: list[list[tuple[str, str]]] = field(default_factory=list)   # inline: (matn, callback_data)
    request_contact: bool = False


def _links(db: Session, chat_id: str, verified: bool | None = None) -> list[TelegramLink]:
    stmt = select(TelegramLink).where(TelegramLink.chat_id == chat_id)
    if verified is True:
        stmt = stmt.where(TelegramLink.verified_at.is_not(None))
    elif verified is False:
        stmt = stmt.where(TelegramLink.verified_at.is_(None))
    return list(db.scalars(stmt))


def _patients(db: Session, phone: str) -> list[Patient]:
    rows = db.scalars(select(Patient).where(Patient.status == StatusEnum.active, Patient.merged_into_id.is_(None)).order_by(Patient.full_name))
    return [p for p in rows if normalize_phone(p.phone) == phone]


def start(db: Session, chat_id: str) -> Reply:
    if _links(db, chat_id, verified=True):
        return Reply("Siz ulangansiz. Buyruqlar: /appointments (qabullar), /results (natijalar), /consent (xabarlarga rozilik), /stop (voz kechish).\n"
                     "Вы подключены: /appointments, /results, /consent, /stop.")
    return Reply("Assalomu alaykum! Qabulga yozilishni, eslatmalarni va natijalarni olish uchun telefon raqamingizni ulang.\n"
                 "Здравствуйте! Чтобы получать напоминания и результаты, подключите номер телефона.", request_contact=True)


def contact(db: Session, chat_id: str, from_user_id: int, contact_user_id: int | None, phone_raw: str, ip: str = "telegram") -> Reply:
    """Faqat foydalanuvchining O'Z kontakti qabul qilinadi (boshqaning raqamini yuborib ulab bo'lmaydi)."""
    if contact_user_id is None or contact_user_id != from_user_id:
        return Reply("Iltimos, faqat o'zingizning kontaktingizni yuboring. / Отправьте только свой контакт.", request_contact=True)
    phone = normalize_phone(phone_raw)
    patients = _patients(db, phone) if phone else []
    if not phone or not patients:
        return Reply("Bu raqamga bemor topilmadi. Klinikaga murojaat qiling. / Пациент с этим номером не найден.")
    for p in patients:                        # kutilayotgan (tasdiqlanmagan) ulanishlar
        if not db.scalar(select(TelegramLink.id).where(TelegramLink.chat_id == chat_id, TelegramLink.patient_id == p.id)):
            db.add(TelegramLink(patient_id=p.id, chat_id=chat_id, phone=phone))
    db.flush()
    branch = db.scalar(select(Branch.id).where(Branch.is_default.is_(True))) or db.scalar(select(Branch.id))
    from fastapi import HTTPException

    try:
        otp.send_code(db, ip, phone, "telegram", branch, patients[0].language or "uz")
    except HTTPException:
        return Reply("Juda ko'p urinish. Birozdan keyin qayta urinib ko'ring. / Слишком много попыток, повторите позже.")
    db.commit()
    return Reply("SMS orqali 6 raqamli kod yubordik. Kodni shu yerga yozing. / Отправили SMS с 6-значным кодом: введите его здесь.")


def _pending_phone(db: Session, chat_id: str) -> str | None:
    pend = _links(db, chat_id, verified=False)
    return pend[0].phone if pend else None


def text(db: Session, chat_id: str, body: str) -> Reply:
    body = body.strip()
    if body in ("/start", "/help"):
        return start(db, chat_id)
    phone = _pending_phone(db, chat_id)
    if phone and re.fullmatch(r"\d{6}", body):
        from fastapi import HTTPException

        try:
            otp.verify_code(db, phone, "telegram", body)
        except HTTPException as exc:
            return Reply(f"{exc.detail}. / Неверный код.")
        now = datetime.now(UTC)
        for link in _links(db, chat_id, verified=False):
            link.verified_at = now
        db.commit()
        return Reply("Telefon tasdiqlandi ✅. Eslatmalarni olish uchun /consent buyrug'i bilan rozilik bering. / Телефон подтверждён. Для напоминаний: /consent.")
    verified = _links(db, chat_id, verified=True)
    if not verified:
        return start(db, chat_id)
    cmd = body.split()[0].lower()
    if cmd == "/appointments":
        return appointments(db, chat_id)
    if cmd == "/results":
        return results(db, chat_id)
    if cmd == "/consent":
        for link in verified:
            _set_consent(db, link.patient_id, True)
        db.commit()
        return Reply("Telegram orqali eslatmalar olishga rozilik qayd etildi ✅. Voz kechish: /stop")
    if cmd == "/stop":
        for link in verified:
            _set_consent(db, link.patient_id, False)
        db.commit()
        return Reply("Telegram xabarlaridan voz kechildi. Qayta yoqish: /consent")
    return Reply("Buyruqlar: /appointments, /results, /consent, /stop")


def _set_consent(db: Session, patient_id: uuid.UUID, granted: bool) -> None:
    from app.routers.messaging import set_consent

    set_consent(db, patient_id, Channel.telegram, granted, "bot")


def appointments(db: Session, chat_id: str) -> Reply:
    links = _links(db, chat_id, verified=True)
    now = datetime.now(UTC)
    rows = db.scalars(select(Appointment).where(Appointment.patient_id.in_([lk.patient_id for lk in links]), Appointment.status == AppointmentStatus.scheduled,
                                                Appointment.starts_at > now).order_by(Appointment.starts_at).limit(10)).all()
    if not rows:
        return Reply("Yaqin qabullar yo'q. / Ближайших приёмов нет.")
    lines, buttons = [], []
    for a in rows:
        local = a.starts_at.astimezone(CLINIC_TZ)
        who = db.get(Patient, a.patient_id).full_name.split()[0]
        lines.append(f"{local:%d.%m.%Y %H:%M} · {db.get(Staff, a.doctor_id).full_name} · {who}" + (" ✅" if a.confirmed_at else ""))
        buttons.append([(f"✅ {local:%d.%m %H:%M}", f"c:{a.id}"), (f"❌ {local:%d.%m %H:%M}", f"x:{a.id}")])
    return Reply("\n".join(lines), buttons)


def results(db: Session, chat_id: str) -> Reply:
    """Faqat telefon tasdiqlangan ulanish va faqat shifokor tasdiqlagan natijalar."""
    links = _links(db, chat_id, verified=True)
    orders = db.scalars(select(LabOrder).where(LabOrder.patient_id.in_([lk.patient_id for lk in links]), LabOrder.status == LabOrderStatus.completed,
                                               LabOrder.approved_at.is_not(None)).order_by(LabOrder.created_at.desc()).limit(3)).all()
    if not orders:
        return Reply("Tasdiqlangan natijalar yo'q. / Подтверждённых результатов нет.")
    from app.routers.lab import order_out

    parts = []
    for o in orders:
        full = order_out(db, o)
        parts.append(f"{full['created_at'][:10]} · {full['patient_name']}\n" + "\n".join(
            f"• {i['name']}: {i['value']} {i['unit'] or ''}" + (f" ({i['reference']})" if i['reference'] else "") + ("  ⚠️" if i["flag"] in ("Low", "High") else "")
            for i in full["items"] if i["value"] is not None))
    return Reply("\n\n".join(parts))


def callback(db: Session, chat_id: str, data: str, request_obj=None) -> Reply:
    links = _links(db, chat_id, verified=True)
    if not links:
        return start(db, chat_id)
    try:
        action, raw = data.split(":", 1)
        appt = db.scalar(select(Appointment).where(Appointment.id == uuid.UUID(raw), Appointment.patient_id.in_([lk.patient_id for lk in links])).with_for_update())
    except ValueError:
        appt = None
    if not appt or appt.status != AppointmentStatus.scheduled or appt.starts_at <= datetime.now(UTC):
        return Reply("Qabul topilmadi yoki faol emas. / Приём не найден или неактивен.")
    if action == "c":
        appt.confirmed_at = appt.confirmed_at or datetime.now(UTC)
        db.commit()
        return Reply("Qabul tasdiqlandi ✅")
    from app.routers.public import cancel_appointment

    cancel_appointment(db, appt, "bot", request_obj)
    return Reply("Qabul bekor qilindi ❌. Vaqt bo'shadi.")
