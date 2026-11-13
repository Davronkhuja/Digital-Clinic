# ruff: noqa: E501
import uuid
from datetime import UTC, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Message, MessageTemplate, PatientConsent
from app.schemas.enums import Channel, ConsentStatus, MessageStatus
from app.schemas.messaging import ConsentIn, LanguageIn, MessageOut, MessageStats, PatientContact, TemplateIn, TemplateOut
from app.services import audit, messaging
from app.services.lookup import get_patient_or_404
from app.services.message_defaults import DEFAULTS, KEYS, LANGUAGES
from app.services.periods import CLINIC_TZ, clinic_today

router = APIRouter()
TAG = "💬 Messaging"
PLACEHOLDERS = {"reminder_24h": ["clinic", "patient", "doctor", "date", "time", "link"], "reminder_2h": ["clinic", "patient", "doctor", "date", "time", "link"],
                "otp": ["clinic", "code"], "booking_confirmation": ["clinic", "patient", "doctor", "date", "time", "link"],
                "waitlist_offer": ["clinic", "patient", "doctor", "date", "time", "link"], "recall": ["clinic", "patient", "doctor", "link"]}


def _consent_out(c: PatientConsent) -> dict:
    return {"channel": c.channel, "status": c.status, "granted_at": c.granted_at, "revoked_at": c.revoked_at, "source": c.source, "note": c.note}


def contact_out(db: Session, patient) -> dict:
    rows = {c.channel: c for c in db.scalars(select(PatientConsent).where(PatientConsent.patient_id == patient.id))}
    out = [_consent_out(rows[ch]) if ch in rows else {"channel": ch, "status": ConsentStatus.revoked, "granted_at": None, "revoked_at": None,
                                                      "source": None, "note": None} for ch in Channel]
    return {"patient_id": str(patient.id), "language": patient.language, "consents": out, "telegram_linked": bool(messaging.telegram_chat(db, patient.id))}


def set_consent(db: Session, patient_id: uuid.UUID, channel: Channel, granted: bool, source: str, note: str | None = None) -> PatientConsent:
    now = datetime.now(UTC)
    c = db.scalar(select(PatientConsent).where(PatientConsent.patient_id == patient_id, PatientConsent.channel == channel))
    if not c:
        c = PatientConsent(patient_id=patient_id, channel=channel, status=ConsentStatus.revoked, source=source)
        db.add(c)
    c.status = ConsentStatus.granted if granted else ConsentStatus.revoked
    if granted:
        c.granted_at, c.revoked_at = now, None
    else:
        c.revoked_at = now
    c.source, c.note = source, note
    db.flush()
    return c


@router.get("/patients/{patient_id}/contact-preferences", tags=[TAG], response_model=PatientContact, summary="Bemorning aloqa roziligi va tili")
def get_contact(patient_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(require("patients:read"))):
    return contact_out(db, get_patient_or_404(db, patient_id))


@router.put("/patients/{patient_id}/consents", tags=[TAG], response_model=PatientContact, summary="Kanal roziligini berish yoki voz kechish",
            description="Rozilik bo'lmasa xabar yuborilmaydi; voz kechilsa navbatdagi xabarlar yuborish paytida o'tkazib yuboriladi (`Skipped`). Kim va qachon auditda.")
def put_consent(patient_id: uuid.UUID, data: ConsentIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("patients:write"))):
    patient = get_patient_or_404(db, patient_id)
    set_consent(db, patient.id, data.channel, data.granted, "staff", data.note)
    audit.record(db, user, request, "update", "consent", patient.id, {"channel": data.channel.value, "granted": data.granted, "note": data.note})
    db.commit()
    return contact_out(db, patient)


@router.put("/patients/{patient_id}/language", tags=[TAG], response_model=PatientContact, summary="Xabarlar tili (uz lotin / ru)")
def put_language(patient_id: uuid.UUID, data: LanguageIn, db: Session = Depends(get_db), user: CurrentUser = Depends(require("patients:write"))):
    patient = get_patient_or_404(db, patient_id)
    patient.language = data.language
    db.commit()
    return contact_out(db, patient)


def _template_out(key: str, lang: str, row: MessageTemplate | None) -> dict:
    return {"key": key, "language": lang, "body": row.body if row else DEFAULTS[(key, lang)], "is_active": row.is_active if row else True,
            "is_default": row is None, "placeholders": PLACEHOLDERS[key]}


@router.get("/message-templates", tags=[TAG], response_model=List[TemplateOut], summary="Xabar shablonlari (uz lotin, ru)")
def list_templates(db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:read"))):
    rows = {(t.key, t.language): t for t in db.scalars(select(MessageTemplate))}
    return [_template_out(k, lang, rows.get((k, lang))) for k in KEYS for lang in LANGUAGES]


@router.put("/message-templates/{key}/{language}", tags=[TAG], response_model=TemplateOut, summary="Shablonni tahrirlash",
            description="Joy egalari {clinic}, {patient}, {doctor}, {date}, {time}, {link}, {code}. Noma'lum joy egasi bo'lsa 422.")
def put_template(key: str, language: str, data: TemplateIn, request: Request, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require("settings:write"))):
    if key not in KEYS or language not in LANGUAGES:
        raise HTTPException(404, "Shablon topilmadi")
    import re

    unknown = set(re.findall(r"\{(\w+)\}", data.body)) - set(PLACEHOLDERS[key])
    if unknown:
        raise HTTPException(422, f"Noma'lum joy egasi: {', '.join(sorted(unknown))}")
    row = db.scalar(select(MessageTemplate).where(MessageTemplate.key == key, MessageTemplate.language == language))
    if not row:
        row = MessageTemplate(key=key, language=language, body=data.body, created_by=user.id)
        db.add(row)
    row.body, row.is_active = data.body, data.is_active
    audit.record(db, user, request, "update", "message_template", None, {"key": key, "language": language})
    db.commit()
    return _template_out(key, language, row)


@router.delete("/message-templates/{key}/{language}", tags=[TAG], summary="Shablonni standartga qaytarish")
def reset_template(key: str, language: str, db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:write"))):
    row = db.scalar(select(MessageTemplate).where(MessageTemplate.key == key, MessageTemplate.language == language))
    if row:
        db.delete(row)
        db.commit()
    return {"message": "Standart shablon tiklandi"}


@router.get("/messages", tags=[TAG], response_model=List[MessageOut], summary="Xabarlar logi (holat, qayta urinishlar)")
def list_messages(status: Optional[MessageStatus] = None, kind: Optional[str] = None, patient_id: Optional[uuid.UUID] = None,
                  limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), user: CurrentUser = Depends(require("messages:read"))):
    from app.models import Patient

    stmt = select(Message, Patient.full_name).outerjoin(Patient, Message.patient_id == Patient.id).order_by(Message.created_at.desc()).limit(limit)
    stmt = stmt.where(Message.branch_id == user.branch_id)
    if status:
        stmt = stmt.where(Message.status == status)
    if kind:
        stmt = stmt.where(Message.kind == kind)
    if patient_id:
        stmt = stmt.where(Message.patient_id == patient_id)
    return [{"id": str(m.id), "patient_id": str(m.patient_id) if m.patient_id else None, "patient_name": name, "channel": m.channel,
             "to_address": m.to_address if m.kind != "otp" else "***" + m.to_address[-4:], "kind": m.kind, "language": m.language,
             "body": m.body if m.kind != "otp" else "(OTP kodi yashirilgan)", "status": m.status, "scheduled_at": m.scheduled_at, "sent_at": m.sent_at,
             "attempts": m.attempts, "last_error": m.last_error, "skip_reason": m.skip_reason, "sms_segments": m.sms_segments,
             "appointment_id": str(m.appointment_id) if m.appointment_id else None} for m, name in db.execute(stmt).all()]


@router.get("/messages/stats", tags=[TAG], response_model=MessageStats, summary="Xabarlar statistikasi va SMS hisobi (xarajat)")
def message_stats(date_from: Optional[str] = None, date_to: Optional[str] = None, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require("messages:read"))):
    try:
        end = datetime.fromisoformat(date_to).date() if date_to else clinic_today()
        start = datetime.fromisoformat(date_from).date() if date_from else end - timedelta(days=29)
    except ValueError:
        raise HTTPException(422, "Sana YYYY-MM-DD bo'lishi kerak")
    lo = datetime.combine(start, datetime.min.time(), tzinfo=CLINIC_TZ)
    hi = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=CLINIC_TZ)
    cond = (Message.created_at >= lo, Message.created_at < hi, Message.branch_id == user.branch_id)
    by_status = dict(db.execute(select(Message.status, func.count()).where(*cond).group_by(Message.status)).all())
    by_kind = dict(db.execute(select(Message.kind, func.count()).where(*cond).group_by(Message.kind)).all())
    sms_n, sms_seg = db.execute(select(func.count(), func.coalesce(func.sum(Message.sms_segments), 0)).where(
        *cond, Message.channel == Channel.sms, Message.status == MessageStatus.sent)).one()
    tg = db.scalar(select(func.count()).where(*cond, Message.channel == Channel.telegram, Message.status == MessageStatus.sent))
    return {"date_from": start.isoformat(), "date_to": end.isoformat(), "by_status": {k.value: v for k, v in by_status.items()},
            "sms_messages": sms_n, "sms_segments": int(sms_seg), "telegram_messages": tg or 0, "by_kind": by_kind}
