from typing import List, Optional  # noqa: F401

from pydantic import BaseModel, EmailStr, Field  # noqa: F401

from app.schemas.enums import *  # noqa: F403


# EMR
class EMRCreate(BaseModel):
    patient_id: str = Field(..., examples=["1"])
    patient_name: str = Field(..., examples=["Aziza Karimova"])
    doctor: str = Field(..., examples=["Dr. Rustamov"])
    diagnosis: str = Field(..., examples=["Gipertenziya 2-darajali"])
    prescription: str = Field(..., examples=["Amlodipine 5mg kuniga 1 marta"])
    notes: Optional[str] = Field(None, examples=["Qon bosimi nazorat ostida"])
    visit_date: str = Field(..., examples=["2026-02-23"])

class EMRRecord(EMRCreate):
    id: str
    created_at: str
