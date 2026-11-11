import uuid
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class EMRCreate(BaseModel):
    patient_id: uuid.UUID = Field(..., examples=["3f2b8c1e-0000-0000-0000-000000000000"])
    patient_name: Optional[str] = Field(None, description="E'tiborga olinmaydi")
    doctor_id: Optional[uuid.UUID] = None
    doctor: Optional[str] = Field(None, examples=["Dr. Rustamov"])
    diagnosis: str = Field(..., examples=["Gipertenziya 2-darajali"])
    icd_code: Optional[str] = Field(None, max_length=10, examples=["I10"])
    prescription: str = Field(..., examples=["Amlodipine 5mg kuniga 1 marta"])
    notes: Optional[str] = Field(None, examples=["Qon bosimi nazorat ostida"])
    complaints: Optional[str] = None
    anamnesis: Optional[str] = None
    examination: Optional[str] = None
    recommendations: Optional[str] = None
    appointment_id: Optional[uuid.UUID] = Field(None, description="Berilsa, qabul `Completed` bo'ladi")
    visit_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["2026-02-23"])

    @model_validator(mode="after")
    def _doctor_required(self):
        if not self.doctor_id and not (self.doctor and self.doctor.strip()):
            raise ValueError("doctor_id yoki doctor ko'rsatilishi kerak")
        return self


class EMRRecord(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor: str
    diagnosis: str
    icd_code: Optional[str] = None
    prescription: str
    notes: Optional[str] = None
    complaints: Optional[str] = None
    anamnesis: Optional[str] = None
    examination: Optional[str] = None
    recommendations: Optional[str] = None
    appointment_id: Optional[str] = None
    visit_date: str
    created_at: str


class Icd10Out(BaseModel):
    code: str
    name_uz: str
    name_en: Optional[str] = None


class EMRUpdate(BaseModel):
    """Ko'rikni tahrirlash. Yuborilmagan maydonlar o'zgarmaydi; retsept alohida (v1.6.11)."""

    diagnosis: Optional[str] = Field(None, min_length=1)
    icd_code: Optional[str] = Field(None, max_length=10)
    complaints: Optional[str] = None
    anamnesis: Optional[str] = None
    examination: Optional[str] = None
    recommendations: Optional[str] = None
    notes: Optional[str] = None


class ExamTemplateIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, examples=["Terapevt: umumiy ko'rik"])
    specialty: Optional[str] = Field(None, max_length=100)
    complaints: Optional[str] = None
    anamnesis: Optional[str] = None
    examination: Optional[str] = None
    diagnosis: Optional[str] = None
    recommendations: Optional[str] = None
    is_active: bool = True


class ExamTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    specialty: Optional[str] = Field(None, max_length=100)
    complaints: Optional[str] = None
    anamnesis: Optional[str] = None
    examination: Optional[str] = None
    diagnosis: Optional[str] = None
    recommendations: Optional[str] = None
    is_active: Optional[bool] = None


class ExamTemplateOut(ExamTemplateIn):
    id: str
