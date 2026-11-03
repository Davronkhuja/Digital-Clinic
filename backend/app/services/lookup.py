import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Patient, Staff
from app.schemas.enums import StaffRole


def resolve_doctor(db: Session, doctor_id: uuid.UUID | None, doctor_name: str | None) -> Staff:
    """Shifokorni ID yoki nom bo'yicha topadi (frontend hozircha nom yuboradi)."""
    if doctor_id:
        staff = db.get(Staff, doctor_id)
    else:
        name = (doctor_name or "").strip().lower()
        staff = db.scalar(
            select(Staff).where(func.lower(Staff.full_name) == name, Staff.role == StaffRole.doctor)
        )
    if not staff or staff.role != StaffRole.doctor:
        raise HTTPException(422, "Shifokor topilmadi")
    return staff


def get_patient_or_404(db: Session, patient_id: uuid.UUID) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(404, "Bemor topilmadi")
    return patient


def resolve_patient_by_name(db: Session, name: str | None) -> Patient | None:
    if not name or not name.strip():
        return None
    matches = db.scalars(select(Patient).where(func.lower(Patient.full_name) == name.strip().lower())).all()
    if len(matches) > 1:
        raise HTTPException(409, f"'{name}' nomli bir nechta bemor bor; patient_id yuboring")
    return matches[0] if matches else None
