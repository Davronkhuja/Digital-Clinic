# ruff: noqa: E501
"""Qabul eslatmalari: 24 soat va 2 soat oldin. Har `Scheduled` qabul uchun har tur bir marta (dedupe). Rozilik/aloqa yo'q bo'lsa `Skipped`
yoziladi (kelmay qolish hisobotida "eslatma yuborilmagan" kesimi uchun). Tungi vaqtda yuborilmaydi: ertalabga suriladi, lekin qabul
boshlanishidan keyinga qolsa `Skipped` (yuborish paytida tekshiriladi)."""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Appointment, ClinicSettings, Patient, Staff
from app.schemas.enums import AppointmentStatus
from app.services import messaging
from app.services.links import appointment_link
from app.services.periods import CLINIC_TZ

KINDS = {"reminder_24h": timedelta(hours=24), "reminder_2h": timedelta(hours=2)}


def _vars(db: Session, appt: Appointment, patient: Patient, clinic_name: str) -> dict:
    local = appt.starts_at.astimezone(CLINIC_TZ)
    doctor = db.get(Staff, appt.doctor_id)
    return {"clinic": clinic_name, "patient": patient.full_name.split()[0] if patient.full_name else "", "doctor": doctor.full_name,
            "date": local.strftime("%d.%m.%Y"), "time": local.strftime("%H:%M"), "link": appointment_link(appt.id, appt.starts_at)}


def reminder_body(db: Session, appt: Appointment, patient: Patient, kind: str, clinic_name: str) -> str:
    return messaging.render(db, kind, patient.language or "uz", **_vars(db, appt, patient, clinic_name))


def schedule_reminders(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Yaqinlashayotgan qabullar uchun eslatmalarni navbatga qo'yadi (idempotent: dedupe). Qabul boshlanishidan o'tgan eslatma vaqti
    (qabul 24 soatdan kam qolganda yozilgan) bo'lsa darhol, tungi vaqtda ertalabga."""
    now = now or datetime.now(UTC)
    horizon = now + timedelta(hours=25)
    appts = db.scalars(select(Appointment).where(Appointment.status == AppointmentStatus.scheduled, Appointment.starts_at > now,
                                                 Appointment.starts_at <= horizon).order_by(Appointment.starts_at)).all()
    stats = {"queued": 0, "skipped": 0, "existing": 0}
    names: dict[uuid.UUID, str] = {}
    for appt in appts:
        patient = db.get(Patient, appt.patient_id)
        if appt.branch_id not in names:
            row = db.scalar(select(ClinicSettings).where(ClinicSettings.branch_id == appt.branch_id))
            names[appt.branch_id] = row.clinic_name if row else "Klinika"
        for kind, before in KINDS.items():
            due = appt.starts_at - before
            if due > now:                      # hali vaqti kelmagan: keyingi aylanishda
                continue
            if kind == "reminder_24h" and appt.created_at and appt.starts_at - appt.created_at.astimezone(UTC) < timedelta(hours=24):
                continue                       # 24 soatdan kam qolganda yozilgan: faqat 2 soatlik eslatma
            msg = messaging.enqueue(db, branch_id=appt.branch_id, kind=kind, body=reminder_body(db, appt, patient, kind, names[appt.branch_id]),
                                    patient=patient, scheduled_at=max(due, now), appointment_id=appt.id,
                                    dedupe_key=f"{kind}:{appt.id}", language=patient.language or "uz")
            if msg is None:
                stats["existing"] += 1
            else:
                stats["skipped" if msg.status.value == "Skipped" else "queued"] += 1
    db.commit()
    return stats

