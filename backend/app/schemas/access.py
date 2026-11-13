from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class RoleOut(BaseModel):
    id: str
    code: str
    name: str
    is_system: bool
    permissions: List[str]
    users_count: int


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=80)
    permissions: List[str]


class PermissionOut(BaseModel):
    code: str
    description: Optional[str] = None


class UserOut(BaseModel):
    id: str
    staff_id: str
    name: str
    email: str
    role: str
    is_active: bool
    branch_id: Optional[str] = None
    branch: Optional[str] = None
    last_login_at: Optional[str] = None


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    branch_id: Optional[str] = Field(None, description="Xodimni boshqa filialga biriktirish (`branches:manage`)")


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, examples=["Ahmad Karimov"])
    email: EmailStr = Field(..., examples=["ahmad@clinic.uz"])
    password: str = Field(..., min_length=8, max_length=72)
    role: str = Field(..., examples=["receptionist"])
    department: Optional[str] = None
    phone: Optional[str] = None
    branch_id: Optional[str] = Field(None, description="Filial (bo'sh: joriy faol filial); boshqa filial uchun `branches:manage`")


class BranchIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, examples=["Chilonzor filiali"])
    address: Optional[str] = Field(None, max_length=300)
    phone: Optional[str] = Field(None, max_length=40)


class BranchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    address: Optional[str] = Field(None, max_length=300)
    phone: Optional[str] = Field(None, max_length=40)
    is_active: Optional[bool] = None


class BranchOut(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    is_default: bool
    is_active: bool
    users_count: int
    current: bool = Field(..., description="Hozirgi so'rovning faol filiali")
