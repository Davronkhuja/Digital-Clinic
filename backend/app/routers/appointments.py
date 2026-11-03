import uuid
from datetime import date, time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Appointment
from app.schemas import Appointment as AppointmentOut
from app.schemas import AppointmentCreate, AppointmentStatus
from app.services import queries
from app.services.lookup import get_patient_or_404, resolve_doctor

router = APIRouter()


@router.get("/appointments", tags=["📅 Appointments"], response_model=List[AppointmentOut],
            summary="Uchrashuvlar ro'yxati")
def get_appointments(
    date: Optional[str] = Query(None, description="Sana bo'yicha filter (YYYY-MM-DD)"),
    doctor: Optional[str] = Query(None, description="Shifokor bo'yicha filter"),
    status: Optional[AppointmentStatus] = Query(None, description="Status bo'yicha filter"),
    patient_id: Optional[uuid.UUID] = Query(None, description="Bemor ID bo'yicha filter"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require("appointments:read")),
):
    try:
        return queries.list_appointments(db, date, doctor, status, patient_id)
    except ValueError:
        raise HTTPException(422, "date YYYY-MM-DD formatida bo'lishi kerak")


@router.post("/appointments", tags=["📅 Appointments"], response_model=AppointmentOut, status_code=201,
             summary="Uchrashuv rejalashtirish")
def create_appointment(data: AppointmentCreate, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require("appointments:write"))):
    patient = get_patient_or_404(db, data.patient_id)
    doctor = resolve_doctor(db, data.doctor_id, data.doctor)
    try:
        appt = Appointment(
            patient_id=patient.id, doctor_id=doctor.id, date=date.fromisoformat(data.date),
            time=time.fromisoformat(data.time), type=data.type, notes=data.notes,
            branch_id=user.branch_id, created_by=user.id,
        )
    except ValueError:
        raise HTTPException(422, "Sana yoki vaqt noto'g'ri")
    db.add(appt)
    db.commit()
    return queries.list_appointments(db, appt_id=appt.id)[0]


@router.patch("/appointments/{appt_id}/status", tags=["📅 Appointments"], response_model=AppointmentOut,
              summary="Uchrashuv statusini o'zgartirish")
def update_appointment_status(appt_id: uuid.UUID, status: AppointmentStatus, db: Session = Depends(get_db),
                              user: CurrentUser = Depends(require("appointments:write"))):
    appt = db.get(Appointment, appt_id)
    if not appt:
        raise HTTPException(404, "Uchrashuv topilmadi")
    appt.status = status
    db.commit()
    return queries.list_appointments(db, appt_id=appt_id)[0]


@router.delete("/appointments/{appt_id}", tags=["📅 Appointments"], summary="Uchrashuvni bekor qilish")
def delete_appointment(appt_id: uuid.UUID, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require("appointments:write"))):
    appt = db.get(Appointment, appt_id)
    if not appt:
        raise HTTPException(404, "Uchrashuv topilmadi")
    db.delete(appt)
    db.commit()
    return {"message": "Uchrashuv bekor qilindi"}
