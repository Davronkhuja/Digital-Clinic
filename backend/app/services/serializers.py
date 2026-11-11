from datetime import date, datetime

from app.models import Appointment, Encounter, Patient, Prescription, Staff, Transaction
from app.services.periods import CLINIC_TZ


def _d(value: date | datetime | None) -> str | None:
    return value.date().isoformat() if isinstance(value, datetime) else (value.isoformat() if value else None)


def age_from(birth: date | None) -> int | None:
    if not birth:
        return None
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def patient_out(p: Patient, doctor_name: str | None, last_visit: date | None) -> dict:
    return {
        "id": str(p.id), "name": p.full_name, "phone": p.phone, "age": age_from(p.birth_date),
        "birth_date": p.birth_date, "gender": p.gender, "pinfl": p.pinfl, "doctor": doctor_name,
        "address": p.address, "blood_type": p.blood_type, "allergies": p.allergies, "status": p.status,
        "last_visit": _d(last_visit),
        "merged_into": str(p.merged_into_id) if p.merged_into_id else None, "created_at": _d(p.created_at),
    }


def appointment_out(a: Appointment, patient_name: str, doctor_name: str, room_name: str | None = None) -> dict:
    return {
        "id": str(a.id), "patient_id": str(a.patient_id), "patient_name": patient_name,
        "doctor_id": str(a.doctor_id), "doctor": doctor_name, "date": a.date.isoformat(),
        "time": a.time.strftime("%H:%M"), "end_time": a.ends_at.astimezone(CLINIC_TZ).strftime("%H:%M"),
        "duration_min": a.duration_min, "starts_at": a.starts_at.isoformat(),
        "room_id": str(a.room_id) if a.room_id else None, "room": room_name, "type": a.type, "notes": a.notes, "status": a.status,
        "created_at": _d(a.created_at),
    }


ROUTE_UZ = {
    "Oral": "ichga", "Intravenous": "vena ichiga", "Intramuscular": "mushak ichiga", "Subcutaneous": "teri ostiga",
    "Topical": "tashqi", "Inhalation": "ingalyatsiya", "Sublingual": "til ostiga", "Rectal": "to'g'ri ichakka",
    "Ophthalmic": "ko'zga", "Nasal": "burunga", "Otic": "quloqqa", "Vaginal": "qinga",
}


def prescription_summary(inn: str, dose: str, route, frequency: str, duration_days: int) -> str:
    """Yig'ma matn (ro'yxat va DMED ga ko'chirish uchun): 'amlodipine 5 mg, ichga, kuniga 1 marta, 30 kun'."""
    return f"{inn} {dose}, {ROUTE_UZ.get(getattr(route, 'value', route), route)}, {frequency}, {duration_days} kun"


def prescription_out(p: Prescription) -> dict:
    return {
        "id": str(p.id), "encounter_id": str(p.encounter_id), "inn": p.inn, "dose": p.dosage, "route": p.route,
        "frequency": p.frequency, "duration_days": p.duration_days, "instructions": p.instructions,
        "medication": p.medication, "created_at": _d(p.created_at),
    }


def encounter_out(e: Encounter, patient_name: str, doctor_name: str, prescription: str,
                  prescriptions: list[Prescription] | None = None) -> dict:
    return {
        "prescriptions": [prescription_out(p) for p in prescriptions or []],
        "id": str(e.id), "patient_id": str(e.patient_id), "patient_name": patient_name,
        "doctor_id": str(e.doctor_id), "doctor": doctor_name, "diagnosis": e.diagnosis,
        "icd_code": e.icd_code, "prescription": prescription, "notes": e.notes, "complaints": e.complaints,
        "anamnesis": e.anamnesis, "examination": e.examination, "recommendations": e.recommendations,
        "appointment_id": str(e.appointment_id) if e.appointment_id else None,
        "visit_date": e.visit_date.isoformat(), "created_at": _d(e.created_at),
    }


def transaction_out(t: Transaction, patient_name: str | None) -> dict:
    return {
        "id": str(t.id), "type": t.type, "amount": t.amount, "description": t.description,
        "patient_id": str(t.patient_id) if t.patient_id else None, "patient_name": patient_name,
        "category": t.category, "date": t.date.isoformat(), "created_at": _d(t.created_at),
    }


def staff_out(s: Staff, patients_count: int) -> dict:
    return {
        "id": str(s.id), "name": s.full_name, "role": s.role, "department": s.department, "phone": s.phone,
        "email": s.email, "schedule": s.schedule, "slot_minutes": s.slot_minutes,
        "default_room_id": str(s.default_room_id) if s.default_room_id else None, "status": s.status, "joined_date": _d(s.joined_date),
        "patients_count": patients_count,
    }
