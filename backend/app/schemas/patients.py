from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.enums import GenderEnum, StatusEnum

SOURCES = ("reklama", "tavsiya", "instagram", "onlayn", "boshqa")


class PatientCreate(BaseModel):
    name: str = Field(..., min_length=2, examples=["Aziza Karimova"])
    phone: str = Field(..., examples=["+998 90 123 4567"])
    age: Optional[int] = Field(None, ge=0, le=150, examples=[34])
    birth_date: Optional[date] = None
    gender: GenderEnum = Field(..., examples=["female"])
    pinfl: Optional[str] = Field(None, examples=["31234567890123"])
    doctor: Optional[str] = Field(None, examples=["Dr. Rustamov"])
    address: Optional[str] = Field(None, examples=["Toshkent, Yunusobod"])
    blood_type: Optional[str] = Field(None, examples=["A+"])
    allergies: Optional[str] = Field(None, examples=["Penisilin"])
    source: Optional[Literal["reklama", "tavsiya", "instagram", "onlayn", "boshqa"]] = Field(None, description="Bemor manbasi")

    @field_validator("pinfl", "birth_date", "doctor", "address", "blood_type", "allergies", "source", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("pinfl")
    @classmethod
    def _pinfl_format(cls, v):
        if v is not None and not (len(v) == 14 and v.isdigit()):
            raise ValueError("PINFL 14 ta raqamdan iborat bo'lishi kerak")
        return v

    @model_validator(mode="after")
    def _age_or_birth_date(self):
        if self.age is None and self.birth_date is None:
            raise ValueError("age yoki birth_date ko'rsatilishi kerak")
        return self


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    birth_date: Optional[date] = None
    gender: Optional[GenderEnum] = None
    pinfl: Optional[str] = None
    doctor: Optional[str] = None
    address: Optional[str] = None
    blood_type: Optional[str] = None
    allergies: Optional[str] = None
    status: Optional[StatusEnum] = None
    source: Optional[Literal["reklama", "tavsiya", "instagram", "onlayn", "boshqa"]] = None

    @field_validator("pinfl", "birth_date", "doctor", "address", "blood_type", "allergies", "source", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("pinfl")
    @classmethod
    def _pinfl_format(cls, v):
        if v is not None and not (len(v) == 14 and v.isdigit()):
            raise ValueError("PINFL 14 ta raqamdan iborat bo'lishi kerak")
        return v


class Patient(BaseModel):
    id: str
    name: str
    phone: str
    age: Optional[int] = None
    birth_date: Optional[date] = None
    gender: GenderEnum
    pinfl: Optional[str] = None
    doctor: Optional[str] = None
    address: Optional[str] = None
    blood_type: Optional[str] = None
    allergies: Optional[str] = None
    source: Optional[str] = None
    status: StatusEnum
    last_visit: Optional[str] = None
    merged_into: Optional[str] = None
    created_at: str


class PatientMerge(BaseModel):
    source_id: str = Field(..., description="Dublikat: uning yozuvlari ushbu bemorga ko'chiriladi")
