from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas.enums import StaffRole, StatusEnum


class StaffCreate(BaseModel):
    name: str = Field(..., examples=["Dr. Behruz Rustamov"])
    role: StaffRole = Field(..., examples=["Doctor"])
    department: str = Field(..., examples=["Kardiologiya"])
    phone: str = Field(..., examples=["+998 90 111 2233"])
    email: EmailStr = Field(..., examples=["rustamov@clinic.uz"])
    schedule: Optional[str] = Field(None, examples=["Dushanba-Juma, 09:00-17:00"])
    slot_minutes: Optional[int] = Field(None, ge=5, le=480, description="Standart qabul davomiyligi (daqiqa)")


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[StaffRole] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    schedule: Optional[str] = None
    slot_minutes: Optional[int] = Field(None, ge=5, le=480)
    default_room_id: Optional[str] = Field(None, description="Shifokorning standart kabineti (null: olib tashlash)")
    status: Optional[StatusEnum] = None


class StaffMember(BaseModel):
    id: str
    name: str
    role: StaffRole
    department: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    schedule: Optional[str] = None
    slot_minutes: int = 30
    default_room_id: Optional[str] = None
    status: StatusEnum
    joined_date: Optional[str] = None
    patients_count: int = 0
