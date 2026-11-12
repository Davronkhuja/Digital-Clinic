import uuid
from typing import Literal, Optional

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
    override_reason: Optional[str] = Field(None, max_length=500, description="Ish vaqtidan tashqari majburan yozish sababi")
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
    override_reason: Optional[str] = None
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
    override_reason: Optional[str] = Field(None, max_length=500)


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


class WaitlistCreate(BaseModel):
    patient_id: uuid.UUID
    doctor_id: Optional[uuid.UUID] = None
    doctor: Optional[str] = Field(None, examples=["Dr. Rustamov"], description="doctor_id bo'lmasa, nom bo'yicha")
    type: str = Field("Konsultatsiya", examples=["Konsultatsiya"])
    date_from: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Bo'lmasa: bugun")
    date_to: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Bo'lmasa: cheklovsiz")
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _doctor_required(self):
        if not self.doctor_id and not (self.doctor and self.doctor.strip()):
            raise ValueError("doctor_id yoki doctor ko'rsatilishi kerak")
        return self


class WaitlistUpdate(BaseModel):
    date_from: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    notes: Optional[str] = None
    status: Optional[Literal["Cancelled"]] = Field(None, description="Faqat bekor qilish; band qilish /book orqali")


class WaitlistBook(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    room_id: Optional[uuid.UUID] = None
    duration_min: Optional[int] = Field(None, ge=5, le=480)
    override_reason: Optional[str] = Field(None, max_length=500)


class WaitlistOut(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    patient_phone: str
    doctor_id: str
    doctor: str
    type: str
    date_from: str
    date_to: Optional[str] = None
    status: str
    appointment_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: str


class WaitlistSuggestion(BaseModel):
    date: str
    time: str
    end_time: str
