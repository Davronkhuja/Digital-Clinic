import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Permission, Role, Staff, User
from app.schemas import PermissionOut, RoleOut, RoleUpdate, UserOut, UserUpdate
from app.services.auth import revoke_all

router = APIRouter()


def _role_out(role: Role, users_count: int) -> dict:
    return {"id": str(role.id), "code": role.code, "name": role.name, "is_system": role.is_system,
            "permissions": sorted(p.code for p in role.permissions), "users_count": users_count}


@router.get("/permissions", tags=["🛡️ Access"], response_model=List[PermissionOut], summary="Ruxsatlar katalogi")
def list_permissions(db: Session = Depends(get_db), user: CurrentUser = Depends(require("roles:manage"))):
    return [{"code": p.code, "description": p.description}
            for p in db.scalars(select(Permission).order_by(Permission.code)).all()]


@router.get("/roles", tags=["🛡️ Access"], response_model=List[RoleOut], summary="Rollar va ularning ruxsatlari")
def list_roles(db: Session = Depends(get_db), user: CurrentUser = Depends(require("roles:manage"))):
    counts = dict(db.execute(select(User.role_id, func.count()).group_by(User.role_id)).all())
    roles = db.scalars(select(Role).order_by(Role.created_at, Role.code)).all()
    return [_role_out(r, counts.get(r.id, 0)) for r in roles]


@router.put("/roles/{role_id}", tags=["🛡️ Access"], response_model=RoleOut, summary="Rol ruxsatlarini yozish",
            description="Administrator roli o'zgartirilmaydi (tizimdan qulflanib qolmaslik uchun).")
def update_role(role_id: uuid.UUID, data: RoleUpdate, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require("roles:manage"))):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Rol topilmadi")
    if role.code == "admin":
        raise HTTPException(400, "Administrator roli o'zgartirilmaydi")
    perms = db.scalars(select(Permission).where(Permission.code.in_(data.permissions))).all()
    unknown = set(data.permissions) - {p.code for p in perms}
    if unknown:
        raise HTTPException(422, f"Noma'lum ruxsatlar: {', '.join(sorted(unknown))}")
    role.permissions = list(perms)
    if data.name:
        role.name = data.name
    db.commit()
    count = db.scalar(select(func.count()).select_from(User).where(User.role_id == role.id))
    return _role_out(role, count)


def _user_out(u: User, staff: Staff, role: Role) -> dict:
    return {"id": str(u.id), "staff_id": str(staff.id), "name": staff.full_name, "email": u.email,
            "role": role.code, "is_active": u.is_active,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None}


@router.get("/users", tags=["🛡️ Access"], response_model=List[UserOut], summary="Foydalanuvchilar (loginlar)")
def list_users(db: Session = Depends(get_db), user: CurrentUser = Depends(require("roles:manage"))):
    rows = db.execute(select(User, Staff, Role).join(Staff, User.staff_id == Staff.id)
                      .join(Role, User.role_id == Role.id).order_by(Staff.full_name)).all()
    return [_user_out(*r) for r in rows]


@router.patch("/users/{user_id}", tags=["🛡️ Access"], response_model=UserOut,
              summary="Foydalanuvchi rolini o'zgartirish yoki faollashtirish/o'chirish")
def update_user(user_id: uuid.UUID, data: UserUpdate, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require("roles:manage"))):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    if target.id == user.id and (data.is_active is False or (data.role and data.role != "admin")):
        raise HTTPException(400, "O'z rolingizni pasaytira yoki o'zingizni o'chira olmaysiz")
    if data.role:
        role = db.scalar(select(Role).where(Role.code == data.role))
        if not role:
            raise HTTPException(422, "Rol topilmadi")
        target.role_id = role.id
    if data.is_active is not None:
        target.is_active = data.is_active
    if data.is_active is False or data.role:
        revoke_all(db, target.id)  # eski huquq bilan yaratilgan sessiyalar tugasin
    db.commit()
    staff = db.get(Staff, target.staff_id)
    return _user_out(target, staff, db.get(Role, target.role_id))
