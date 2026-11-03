from typing import List, Optional

from pydantic import BaseModel, Field


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
    last_login_at: Optional[str] = None


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
