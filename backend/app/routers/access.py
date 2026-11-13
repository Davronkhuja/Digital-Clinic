import uuid
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.core.security import hash_password
from app.db.session import get_db
from app.models import Branch, Permission, Role, Staff, User
from app.schemas import PermissionOut, RoleOut, RoleUpdate, StaffRole, UserCreate, UserOut, UserUpdate
from app.services import audit
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
def update_role(role_id: uuid.UUID, data: RoleUpdate, request: Request, db: Session = Depends(get_db),
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
    audit.record(db, user, request, "update", "role", role.id, {"permissions": sorted(data.permissions)})
    db.commit()
    count = db.scalar(select(func.count()).select_from(User).where(User.role_id == role.id))
    return _role_out(role, count)


def _user_out(u: User, staff: Staff, role: Role, branch: Branch | None = None) -> dict:
    return {"id": str(u.id), "staff_id": str(staff.id), "name": staff.full_name, "email": u.email,
            "role": role.code, "is_active": u.is_active, "branch_id": str(u.branch_id), "branch": branch.name if branch else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None}


@router.get("/users", tags=["🛡️ Access"], response_model=List[UserOut], summary="Foydalanuvchilar (loginlar)")
def list_users(db: Session = Depends(get_db), user: CurrentUser = Depends(require("roles:manage"))):
    rows = db.execute(select(User, Staff, Role, Branch).join(Staff, User.staff_id == Staff.id)
                      .join(Role, User.role_id == Role.id).join(Branch, User.branch_id == Branch.id).order_by(Staff.full_name)).all()
    return [_user_out(*r) for r in rows]


def _target_branch(db: Session, user: CurrentUser, branch_id: str | None) -> Branch:
    """Foydalanuvchi uchun filial: bo'sh bo'lsa joriy faol filial; boshqasi uchun `branches:manage`."""
    if not branch_id or branch_id == str(user.branch_id):
        return db.get(Branch, user.branch_id)
    if "branches:manage" not in user.permissions:
        raise HTTPException(403, "Boshqa filialga biriktirish ruxsati yo'q: branches:manage")
    try:
        branch = db.get(Branch, uuid.UUID(branch_id))
    except ValueError:
        raise HTTPException(422, "branch_id noto'g'ri")
    if not branch or not branch.is_active:
        raise HTTPException(422, "Filial topilmadi yoki faol emas")
    return branch


STAFF_ROLE_FOR = {"admin": StaffRole.admin, "doctor": StaffRole.doctor, "nurse": StaffRole.nurse,
                  "receptionist": StaffRole.receptionist, "senior_receptionist": StaffRole.receptionist,
                  "cashier": StaffRole.cashier}


@router.post("/users", tags=["🛡️ Access"], response_model=UserOut, status_code=201,
             summary="Xodim va login yaratish (faqat administrator)",
             description="Ro'yxatdan o'tish yo'q: xodimni va uning loginini faqat administrator qo'shadi.")
def create_user(data: UserCreate, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("roles:manage"))):
    role = db.scalar(select(Role).where(Role.code == data.role))
    if not role or role.code not in STAFF_ROLE_FOR:
        raise HTTPException(422, "Rol topilmadi")
    email = data.email.lower()
    branch = _target_branch(db, user, data.branch_id)
    staff = Staff(full_name=data.name, role=STAFF_ROLE_FOR[role.code], department=data.department, phone=data.phone,
                  email=email, joined_date=date.today(), branch_id=branch.id, created_by=user.id)
    db.add(staff)
    try:
        db.flush()
        new_user = User(staff_id=staff.id, role_id=role.id, email=email, password_hash=hash_password(data.password),
                        is_active=True, branch_id=branch.id, created_by=user.id)
        db.add(new_user)
        db.flush()
        audit.record(db, user, request, "create", "user", new_user.id, {"role": role.code, "branch": branch.name})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu email bilan xodim yoki foydalanuvchi allaqachon mavjud")
    return _user_out(new_user, staff, role, branch)


@router.patch("/users/{user_id}", tags=["🛡️ Access"], response_model=UserOut,
              summary="Foydalanuvchi rolini o'zgartirish yoki faollashtirish/o'chirish")
def update_user(user_id: uuid.UUID, data: UserUpdate, request: Request, db: Session = Depends(get_db),
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
    if data.branch_id is not None:
        branch = _target_branch(db, user, data.branch_id)
        target.branch_id = branch.id
        db.get(Staff, target.staff_id).branch_id = branch.id        # xodim va uning logini bir filialda
    if data.is_active is False or data.role:
        revoke_all(db, target.id)  # eski huquq bilan yaratilgan sessiyalar tugasin
    audit.record(db, user, request, "update", "user", target.id, data.model_dump(exclude_unset=True))
    db.commit()
    staff = db.get(Staff, target.staff_id)
    return _user_out(target, staff, db.get(Role, target.role_id), db.get(Branch, target.branch_id))
