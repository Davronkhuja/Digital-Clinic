import uuid
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.enums import AppointmentStatus


class AppointmentCreate(BaseModel):
    patient_id: uuid.UUID = Field(..., examples=["3f2b8c1e-0000-0000-0000-000000000000"])
    patient_name: Optional[str] = Field(None, description="E'tiborga olinmaydi: nom bazadan join orqali olinadi")
    doctor_id: Optional[uuid.UUID] = None
    doctor: Optional[str] = Field(None, examples=["Dr. Rustamov"], description="doctor_id bo'lmasa, nom bo'yicha")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["2026-02-25"])
    time: str = Field(..., pattern=r"^\d{2}:\d{2}$", examples=["10:00"])
    type: str = Field(..., examples=["Konsultatsiya"])
    duration_min: Optional[int] = Field(None, ge=5, le=480, description="Bo'lmasa: xizmat turi, so'ng shifokor standarti")
    room_id: Optional[uuid.UUID] = Field(None, description="Bo'lmasa: shifokorning standart kabineti")
    notes: Optional[str] = Field(None, examples=["Qon bosimi tekshiruvi"])

    @model_validator(mode="after")
    def _doctor_required(self):
        if not self.doctor_id and not (self.doctor and self.doctor.strip()):
            raise ValueError("doctor_id yoki doctor ko'rsatilishi kerak")
        return self


class Appointment(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor: str
    date: str
    time: str
    end_time: str
    duration_min: int
    starts_at: str
    type: str
    room_id: Optional[str] = None
    room: Optional[str] = None
    notes: Optional[str] = None
    status: AppointmentStatus
    created_at: str


class AppointmentTypeIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=60, examples=["Konsultatsiya"])
    duration_min: int = Field(30, ge=5, le=480)
    is_active: bool = True


class AppointmentTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=60)
    duration_min: Optional[int] = Field(None, ge=5, le=480)
    is_active: Optional[bool] = None


class AppointmentTypeOut(BaseModel):
    id: str
    name: str
    duration_min: int
    is_active: bool


class AppointmentUpdate(BaseModel):
    """Uchrashuvni ko'chirish/o'zgartirish (faqat `Scheduled`). Yuborilmagan maydonlar o'zgarmaydi."""

    doctor_id: Optional[uuid.UUID] = None
    doctor: Optional[str] = None
    room_id: Optional[uuid.UUID] = Field(None, description="null yuborilsa kabinet olib tashlanadi")
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    type: Optional[str] = None
    duration_min: Optional[int] = Field(None, ge=5, le=480)
    notes: Optional[str] = None


class RoomIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60, examples=["101"])
    description: Optional[str] = Field(None, max_length=200, examples=["Kardiologiya kabineti"])
    is_active: bool = True


class RoomUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=60)
    description: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None


class RoomOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_active: bool
