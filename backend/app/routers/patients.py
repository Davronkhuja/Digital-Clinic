import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Patient
from app.schemas import Patient as PatientOut
from app.schemas import PatientCreate, PatientUpdate, StatusEnum
from app.services import audit, queries
from app.services.lookup import get_patient_or_404, resolve_doctor

router = APIRouter()


def _birth_date(age: int | None, birth_date: date | None) -> date | None:
    if birth_date or age is None:
        return birth_date
    today = date.today()
    try:
        return today.replace(year=today.year - age)
    except ValueError:  # 29-fevral
        return today.replace(year=today.year - age, day=28)


@router.get("/patients", tags=["👥 Patients"], response_model=List[PatientOut], summary="Bemorlar ro'yxati",
            description="Qidiruv (ism, telefon raqamlari, PINFL, tug'ilgan sana) va filtrlash.")
def get_patients(
    request: Request,
    search: Optional[str] = Query(None, description="Ism, telefon, PINFL yoki tug'ilgan sana (YYYY-MM-DD, DD.MM.YYYY)"),
    status: Optional[StatusEnum] = Query(None, description="Status bo'yicha filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require("patients:read")),
):
    result = queries.list_patients(db, search, status, skip, limit)
    audit.record_read(db, user, request, "patient", details={"search": search, "count": len(result)})
    return result


@router.get("/patients/duplicates", tags=["👥 Patients"], summary="Ehtimoliy dublikatlar",
            description="Bir xil ism va (telefon raqamlari yoki tug'ilgan sana) bo'lgan faol bemorlar guruhlari.")
def get_patient_duplicates(request: Request, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(require("patients:read"))):
    groups = queries.patient_duplicate_groups(db)
    audit.record_read(db, user, request, "patient", details={"duplicates": len(groups)})
    return groups


@router.post("/patients", tags=["👥 Patients"], response_model=PatientOut, status_code=201,
             summary="Yangi bemor qo'shish")
def create_patient(data: PatientCreate, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("patients:write"))):
    doctor = resolve_doctor(db, None, data.doctor) if data.doctor else None
    patient = Patient(
        full_name=data.name.strip(), phone=data.phone, birth_date=_birth_date(data.age, data.birth_date),
        gender=data.gender, pinfl=data.pinfl, address=data.address, blood_type=data.blood_type,
        allergies=data.allergies, primary_doctor_id=doctor.id if doctor else None,
        branch_id=user.branch_id, created_by=user.id,
    )
    db.add(patient)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu PINFL bilan bemor allaqachon mavjud")
    audit.record(db, user, request, "create", "patient", patient.id)
    db.commit()
    return queries.get_patient(db, patient.id)


@router.get("/patients/{patient_id}", tags=["👥 Patients"], response_model=PatientOut, summary="Bitta bemor")
def get_patient(patient_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require("patients:read"))):
    result = queries.get_patient(db, patient_id)
    if not result:
        raise HTTPException(404, "Bemor topilmadi")
    audit.record_read(db, user, request, "patient", patient_id)
    return result


@router.put("/patients/{patient_id}", tags=["👥 Patients"], response_model=PatientOut,
            summary="Bemor ma'lumotlarini yangilash")
def update_patient(patient_id: uuid.UUID, data: PatientUpdate, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("patients:write"))):
    patient = get_patient_or_404(db, patient_id)
    fields = data.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"]:
        patient.full_name = fields["name"].strip()
    for key in ("phone", "gender", "pinfl", "address", "blood_type", "allergies", "status"):
        if key in fields and (fields[key] is not None or key in ("pinfl", "address", "blood_type", "allergies")):
            setattr(patient, key, fields[key])
    if "birth_date" in fields or "age" in fields:
        patient.birth_date = _birth_date(fields.get("age"), fields.get("birth_date")) or patient.birth_date
    if "doctor" in fields:
        patient.primary_doctor_id = resolve_doctor(db, None, fields["doctor"]).id if fields["doctor"] else None
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu PINFL bilan bemor allaqachon mavjud")
    audit.record(db, user, request, "update", "patient", patient_id, {"fields": sorted(fields)})
    db.commit()
    return queries.get_patient(db, patient_id)


@router.delete("/patients/{patient_id}", tags=["👥 Patients"], summary="Bemorni o'chirish",
               description="Uchrashuv, EMR yoki to'lovi bor bemorni o'chirib bo'lmaydi (409): faolsizlantiring.")
def delete_patient(patient_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("patients:delete"))):
    patient = get_patient_or_404(db, patient_id)
    try:
        db.delete(patient)
        db.flush()
        audit.record(db, user, request, "delete", "patient", patient_id, {"name": patient.full_name})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bemorda yozuvlar (uchrashuv, EMR yoki to'lov) bor: o'chirib bo'lmaydi, faolsizlantiring")
    return {"message": "Bemor o'chirildi"}
