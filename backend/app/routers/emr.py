import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Encounter, Prescription
from app.schemas import EMRCreate, EMRRecord
from app.services import queries
from app.services.lookup import get_patient_or_404, resolve_doctor

router = APIRouter()


@router.get("/emr", tags=["📋 EMR"], response_model=List[EMRRecord], summary="Tibbiy yozuvlar ro'yxati")
def get_emr(patient_id: Optional[uuid.UUID] = Query(None), db: Session = Depends(get_db),
            user: CurrentUser = Depends(require("emr:read"))):
    return queries.list_encounters(db, patient_id)


@router.post("/emr", tags=["📋 EMR"], response_model=EMRRecord, status_code=201,
             summary="Yangi tibbiy yozuv qo'shish")
def create_emr(data: EMRCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(require("emr:write"))):
    patient = get_patient_or_404(db, data.patient_id)
    doctor = resolve_doctor(db, data.doctor_id, data.doctor)
    try:
        visit_date = date.fromisoformat(data.visit_date)
    except ValueError:
        raise HTTPException(422, "visit_date noto'g'ri")
    enc = Encounter(patient_id=patient.id, doctor_id=doctor.id, visit_date=visit_date, icd_code=data.icd_code,
                    diagnosis=data.diagnosis, notes=data.notes, branch_id=user.branch_id, created_by=user.id)
    db.add(enc)
    db.flush()
    if data.prescription.strip() and data.prescription.strip() != "-":
        db.add(Prescription(encounter_id=enc.id, patient_id=patient.id, medication=data.prescription.strip(),
                            branch_id=user.branch_id, created_by=user.id))
    db.commit()
    return queries.list_encounters(db, record_id=enc.id)[0]


@router.get("/emr/{record_id}", tags=["📋 EMR"], response_model=EMRRecord, summary="Bitta tibbiy yozuv")
def get_emr_record(record_id: uuid.UUID, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("emr:read"))):
    rows = queries.list_encounters(db, record_id=record_id)
    if not rows:
        raise HTTPException(404, "Yozuv topilmadi")
    return rows[0]
