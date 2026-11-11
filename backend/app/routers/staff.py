import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Staff
from app.schemas import StaffCreate, StaffMember, StaffRole, StaffUpdate
from app.services import queries

router = APIRouter()


@router.get("/staff", tags=["👔 Staff"], response_model=List[StaffMember], summary="Xodimlar ro'yxati")
def get_staff(role: Optional[StaffRole] = None, db: Session = Depends(get_db),
              user: CurrentUser = Depends(require("staff:read"))):
    return queries.list_staff(db, role)


@router.post("/staff", tags=["👔 Staff"], response_model=StaffMember, status_code=201,
             summary="Yangi xodim qo'shish")
def create_staff(data: StaffCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(require("staff:write"))):
    from datetime import date

    member = Staff(full_name=data.name, role=data.role, department=data.department, phone=data.phone,
                   email=data.email.lower(), schedule=data.schedule, slot_minutes=data.slot_minutes or 30, joined_date=date.today(),
                   branch_id=user.branch_id, created_by=user.id)
    db.add(member)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu email bilan xodim allaqachon mavjud")
    return queries.list_staff(db, staff_id=member.id)[0]


@router.put("/staff/{staff_id}", tags=["👔 Staff"], response_model=StaffMember,
            summary="Xodim ma'lumotlarini yangilash")
def update_staff(staff_id: uuid.UUID, data: StaffUpdate, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require("staff:write"))):
    member = db.get(Staff, staff_id)
    if not member:
        raise HTTPException(404, "Xodim topilmadi")
    fields = data.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"]:
        member.full_name = fields.pop("name")
    fields.pop("name", None)
    if "email" in fields and fields["email"]:
        fields["email"] = fields["email"].lower()
    for key, value in fields.items():
        if value is not None:
            setattr(member, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu email bilan xodim allaqachon mavjud")
    return queries.list_staff(db, staff_id=staff_id)[0]


@router.delete("/staff/{staff_id}", tags=["👔 Staff"], summary="Xodimni o'chirish",
               description="Yozuvlari (uchrashuv, EMR) bor xodimni o'chirib bo'lmaydi (409): faolsizlantiring.")
def delete_staff(staff_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(require("staff:write"))):
    member = db.get(Staff, staff_id)
    if not member:
        raise HTTPException(404, "Xodim topilmadi")
    if member.id == user.staff_id:
        raise HTTPException(400, "O'zingizni o'chira olmaysiz")
    try:
        db.delete(member)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Xodimda yozuvlar bor: o'chirib bo'lmaydi, faolsizlantiring")
    return {"message": "Xodim o'chirildi"}
