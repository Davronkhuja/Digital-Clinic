from typing import List, Optional  # noqa: F401

from pydantic import BaseModel, EmailStr, Field  # noqa: F401

from app.schemas.enums import *  # noqa: F403


# Patient
class PatientCreate(BaseModel):
    name: str = Field(..., examples=["Aziza Karimova"])
    phone: str = Field(..., examples=["+998 90 123 4567"])
    age: int = Field(..., ge=0, le=150, examples=[34])
    gender: GenderEnum = Field(..., examples=["female"])
    doctor: Optional[str] = Field(None, examples=["Dr. Rustamov"])
    address: Optional[str] = Field(None, examples=["Toshkent, Yunusobod"])
    blood_type: Optional[str] = Field(None, examples=["A+"])
    allergies: Optional[str] = Field(None, examples=["Penisilin"])

class PatientUpdate(PatientCreate):
    name: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[GenderEnum] = None

class Patient(PatientCreate):
    id: str
    status: StatusEnum = StatusEnum.active
    last_visit: Optional[str] = None
    created_at: str
