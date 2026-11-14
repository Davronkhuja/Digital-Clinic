# ruff: noqa: E501
"""Bo'shagan vaqtni kutish ro'yxatidagi bemorga taklif qilish: imzolangan, muddatli havola (login kerak emas).
Qabul bekor qilinganda (havola, portal, bot yoki xodim) birinchi mos va roziligi bor kutuvchiga `waitlist_offer` xabari ketadi."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Appointment, ClinicSettings, Patient, Staff, WaitlistEntry
from app.schemas.enums import WaitlistStatus
from app.services import links, messaging
from app.services.periods import CLINIC_TZ

OFFER_TTL = timedelta(hours=12)
MIN_LEAD = timedelta(minutes=30)  # boshlanishiga 30 daqiqadan kam qolsa taklif qilinmaydi


def offer_link(entry: WaitlistEntry, appt: Appointment, expires: datetime) -> str:
    data = {"entry": str(entry.id), "doctor": str(appt.doctor_id), "room": str(appt.room_id) if appt.room_id else None,
            "starts": appt.starts_at.isoformat(), "type": entry.type}
    return f"{settings.public_base_url}/p/o/{links.make_token('offer', data, expires)}"


def offer_freed_slot(db: Session, appt: Appointment, now: datetime | None = None) -> WaitlistEntry | None:
    """Bekor bo'lgan qabul vaqtini birinchi mos kutuvchiga taklif qiladi (rozilik va aloqa bo'lgan). Taklif qilingan yozuv yoki None."""
    now = now or datetime.now(UTC)
    if appt.starts_at - now < MIN_LEAD:
        return None
    day = appt.starts_at.astimezone(CLINIC_TZ).date()
    entries = db.scalars(select(WaitlistEntry).where(
        WaitlistEntry.doctor_id == appt.doctor_id, WaitlistEntry.branch_id == appt.branch_id, WaitlistEntry.status == WaitlistStatus.waiting, WaitlistEntry.patient_id != appt.patient_id,
        WaitlistEntry.date_from <= day, (WaitlistEntry.date_to.is_(None)) | (WaitlistEntry.date_to >= day)).order_by(WaitlistEntry.created_at)).all()
    doctor = db.get(Staff, appt.doctor_id)
    row = db.scalar(select(ClinicSettings).where(ClinicSettings.branch_id == appt.branch_id))
    local = appt.starts_at.astimezone(CLINIC_TZ)
    for entry in entries:
        patient = db.get(Patient, entry.patient_id)
        if not messaging.pick_channel(db, patient):
            continue                                   # roziligi/aloqasi yo'q: keyingisi
        expires = min(now + OFFER_TTL, appt.starts_at - timedelta(minutes=15))
        body = messaging.render(db, "waitlist_offer", patient.language or "uz", clinic=row.clinic_name if row else "Klinika",
                                patient=(patient.full_name.split() or [""])[0], doctor=doctor.full_name, date=local.strftime("%d.%m.%Y"),
                                time=local.strftime("%H:%M"), link=offer_link(entry, appt, expires))
        msg = messaging.enqueue(db, branch_id=appt.branch_id, kind="waitlist_offer", body=body, patient=patient, scheduled_at=now,
                                appointment_id=None, dedupe_key=f"offer:{appt.id}:{entry.id}", language=patient.language or "uz")
        if msg and msg.status.value == "Queued":
            return entry
    return None


