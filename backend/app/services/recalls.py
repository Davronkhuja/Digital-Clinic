# ruff: noqa: E501
"""Qayta tashrif eslatmasi: shifokor ko'rikda `recall_days` belgilaydi (`recall_date`); shu kuni (klinika vaqti 10:00 dan) bemorga xabar ketadi.
Allaqachon kelajakda rejalashtirilgan qabul bo'lsa yoki shu ko'rikdan keyin kelgan bo'lsa yuborilmaydi. Rozilik, tungi vaqt, dedupe umumiy qoidalar bilan."""
from datetime import UTC, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Appointment, ClinicSettings, Encounter, Patient, Staff
from app.schemas.enums import AppointmentStatus
from app.services import messaging
from app.services.periods import CLINIC_TZ


def schedule_recalls(db: Session, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    today = now.astimezone(CLINIC_TZ).date()
    encounters = db.scalars(select(Encounter).where(Encounter.deleted_at.is_(None), Encounter.recall_date.is_not(None),
                                                    Encounter.recall_date <= today)).all()
    stats = {"queued": 0, "skipped": 0, "existing": 0, "not_needed": 0}
    for enc in encounters:
        patient = db.get(Patient, enc.patient_id)
        future = db.scalar(select(Appointment.id).where(Appointment.patient_id == enc.patient_id, Appointment.status == AppointmentStatus.scheduled,
                                                        Appointment.starts_at > now).limit(1))
        came_back = db.scalar(select(Appointment.id).where(Appointment.patient_id == enc.patient_id, Appointment.starts_at > enc.created_at,
                                                           Appointment.status == AppointmentStatus.completed).limit(1))
        if future or came_back:
            stats["not_needed"] += 1
            continue
        row = db.scalar(select(ClinicSettings).where(ClinicSettings.branch_id == enc.branch_id))
        doctor = db.get(Staff, enc.doctor_id)
        body = messaging.render(db, "recall", patient.language or "uz", clinic=row.clinic_name if row else "Klinika",
                                patient=(patient.full_name.split() or [""])[0], doctor=doctor.full_name, link=f"{settings.public_base_url}/p/book")
        due = datetime.combine(enc.recall_date, time(10, 0), tzinfo=CLINIC_TZ).astimezone(UTC)
        msg = messaging.enqueue(db, branch_id=enc.branch_id, kind="recall", body=body, patient=patient, scheduled_at=max(due, now),
                                dedupe_key=f"recall:{enc.id}", language=patient.language or "uz")
        stats["existing" if msg is None else "skipped" if msg.status.value == "Skipped" else "queued"] += 1
    db.commit()
    return stats
