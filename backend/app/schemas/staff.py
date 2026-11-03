from typing import List, Optional  # noqa: F401

from pydantic import BaseModel, EmailStr, Field  # noqa: F401

from app.schemas.enums import *  # noqa: F403


# Staff
class StaffCreate(BaseModel):
    name: str = Field(..., examples=["Dr. Behruz Rustamov"])
    role: StaffRole = Field(..., examples=["Doctor"])
    department: str = Field(..., examples=["Kardiologiya"])
    phone: str = Field(..., examples=["+998 90 111 2233"])
    email: EmailStr = Field(..., examples=["rustamov@clinic.uz"])
    schedule: Optional[str] = Field(None, examples=["Dushanba-Juma, 09:00-17:00"])

class StaffUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[StaffRole] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    schedule: Optional[str] = None
    status: Optional[StatusEnum] = None

class StaffMember(StaffCreate):
    id: str
    status: StatusEnum = StatusEnum.active
    joined_date: str
    patients_count: int = 0
