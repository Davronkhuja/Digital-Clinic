import csv  # noqa: F401
import io  # noqa: F401
from datetime import date, datetime  # noqa: F401
from typing import List, Optional  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query, status  # noqa: F401
from fastapi.responses import Response  # noqa: F401

from app.core.config import settings  # noqa: F401
from app.core.security import *  # noqa: F401,F403
from app.db import fake  # noqa: F401
from app.schemas import *  # noqa: F401,F403

router = APIRouter()

# ── APPOINTMENTS ──────────────────────────────
@router.get("/appointments", tags=["📅 Appointments"], response_model=List[Appointment],
         summary="Uchrashuvlar ro'yxati", description="Barcha rejalashtirilgan uchrashuvlarni olish.")
def get_appointments(
    date: Optional[str] = Query(None, description="Sana bo'yicha filter (YYYY-MM-DD)"),
    doctor: Optional[str] = Query(None, description="Shifokor bo'yicha filter"),
    status: Optional[AppointmentStatus] = Query(None, description="Status bo'yicha filter"),
    patient_id: Optional[str] = Query(None, description="Bemor ID bo'yicha filter"),
    _=Depends(get_current_user)
):
    results = fake.fake_appointments
    if patient_id:
        results = [a for a in results if a.patient_id == patient_id]
    if date:
        results = [a for a in results if a.date == date]
    if doctor:
        results = [a for a in results if doctor.lower() in a.doctor.lower()]
    if status:
        results = [a for a in results if a.status == status]
    return results

@router.post("/appointments", tags=["📅 Appointments"], response_model=Appointment,
          status_code=201, summary="Uchrashuv rejalashtirish")
def create_appointment(data: AppointmentCreate, _=Depends(get_current_user)):
    appt = Appointment(**data.model_dump(), id=new_id(),
                       created_at=datetime.now().isoformat()[:10])
    fake.fake_appointments.append(appt)
    return appt

@router.patch("/appointments/{appt_id}/status", tags=["📅 Appointments"],
           summary="Uchrashuv statusini o'zgartirish")
def update_appointment_status(appt_id: str, status: AppointmentStatus, _=Depends(get_current_user)):
    for a in fake.fake_appointments:
        if a.id == appt_id:
            a.status = status
            return a
    raise HTTPException(404, "Uchrashuv topilmadi")

@router.delete("/appointments/{appt_id}", tags=["📅 Appointments"], summary="Uchrashuvni bekor qilish")
def delete_appointment(appt_id: str, _=Depends(get_current_user)):
    fake.fake_appointments = [a for a in fake.fake_appointments if a.id != appt_id]
    return {"message": "Uchrashuv bekor qilindi"}
