from typing import List, Optional  # noqa: F401

from pydantic import BaseModel, EmailStr, Field  # noqa: F401

from app.schemas.enums import *  # noqa: F403


# Settings
class ClinicSettings(BaseModel):
    clinic_name: str = Field(..., examples=["Digital Klinika"])
    address: str = Field(..., examples=["Toshkent, Amir Temur ko'chasi 1"])
    phone: str = Field(..., examples=["+998 71 200 0000"])
    email: EmailStr = Field(..., examples=["info@clinic.uz"])
    currency: str = Field(default="UZS", examples=["UZS"])
    timezone: str = Field(default="Asia/Tashkent", examples=["Asia/Tashkent"])
    language: str = Field(default="uz", examples=["uz"])
