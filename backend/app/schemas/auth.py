from typing import List, Optional  # noqa: F401

from pydantic import BaseModel, EmailStr, Field  # noqa: F401

from app.schemas.enums import *  # noqa: F403


# Auth
class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["admin@clinic.uz"])
    password: str = Field(..., min_length=6, examples=["password123"])

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, examples=["Ahmad Karimov"])
    email: EmailStr = Field(..., examples=["ahmad@clinic.uz"])
    password: str = Field(..., min_length=6, examples=["securepass123"])
    clinic_name: str = Field(..., examples=["Hayot Klinnikasi"])

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class RefreshRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., examples=["admin@clinic.uz"])
