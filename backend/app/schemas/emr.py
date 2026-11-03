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
    visit_date: str
    created_at: str
