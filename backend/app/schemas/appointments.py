from typing import List, Optional  # noqa: F401

from pydantic import BaseModel, EmailStr, Field  # noqa: F401

from app.schemas.enums import *  # noqa: F403


# Appointment
class AppointmentCreate(BaseModel):
    patient_id: str = Field(..., examples=["1"])
    patient_name: str = Field(..., examples=["Aziza Karimova"])
    doctor: str = Field(..., examples=["Dr. Rustamov"])
    date: str = Field(..., examples=["2026-02-25"])
    time: str = Field(..., examples=["10:00"])
    type: str = Field(..., examples=["Konsultatsiya"])
    notes: Optional[str] = Field(None, examples=["Qon bosimi tekshiruvi"])

class Appointment(AppointmentCreate):
    id: str
    status: AppointmentStatus = AppointmentStatus.scheduled
    created_at: str
