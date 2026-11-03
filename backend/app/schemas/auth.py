from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["admin@clinic.uz"])
    password: str = Field(..., min_length=6, max_length=72, examples=["password123"])


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, examples=["Ahmad Karimov"])
    email: EmailStr = Field(..., examples=["ahmad@clinic.uz"])
    password: str = Field(..., min_length=8, max_length=72, examples=["securepass123"])
    clinic_name: str = Field(..., examples=["Hayot Klinikasi"])


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., max_length=72)
    new_password: str = Field(..., min_length=8, max_length=72)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., examples=["admin@clinic.uz"])
