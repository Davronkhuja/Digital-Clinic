import csv  # noqa: F401
import io  # noqa: F401
from datetime import date, datetime  # noqa: F401
from typing import List, Optional  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query, status  # noqa: F401
from fastapi.responses import Response  # noqa: F401

from app.core.config import settings  # noqa: F401
from app.core.security import *  # noqa: F401,F403
from app.db import fake  # noqa: F401
from app.schemas import *  # noqa: F401,F403

router = APIRouter()

# ── STAFF ─────────────────────────────────────
@router.get("/staff", tags=["👔 Staff"], response_model=List[StaffMember],
         summary="Xodimlar ro'yxati", description="Barcha klinika xodimlarini ko'rish.")
def get_staff(role: Optional[StaffRole] = None, _=Depends(get_current_user)):
    if role:
        return [s for s in fake.fake_staff if s.role == role]
    return fake.fake_staff

@router.post("/staff", tags=["👔 Staff"], response_model=StaffMember, status_code=201,
          summary="Yangi xodim qo'shish")
def create_staff(data: StaffCreate, _=Depends(get_current_user)):
    member = StaffMember(**data.model_dump(), id=new_id(),
                         joined_date=datetime.now().isoformat()[:10])
    fake.fake_staff.append(member)
    return member

@router.put("/staff/{staff_id}", tags=["👔 Staff"], response_model=StaffMember,
         summary="Xodim ma'lumotlarini yangilash")
def update_staff(staff_id: str, data: StaffUpdate, _=Depends(get_current_user)):
    for member in fake.fake_staff:
        if member.id == staff_id:
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(member, key, value)
            return member
    raise HTTPException(404, "Xodim topilmadi")

@router.delete("/staff/{staff_id}", tags=["👔 Staff"], summary="Xodimni o'chirish")
def delete_staff(staff_id: str, _=Depends(get_current_user)):
    fake.fake_staff = [s for s in fake.fake_staff if s.id != staff_id]
    return {"message": "Xodim o'chirildi"}
