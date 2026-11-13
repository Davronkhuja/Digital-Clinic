# ruff: noqa: E501
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user, require
from app.db.session import get_db
from app.models import Branch, ClinicSettings, StockBatch, User
from app.schemas.access import BranchIn, BranchOut, BranchUpdate
from app.services import audit

router = APIRouter()
TAG = "🏢 Branches (filiallar)"


def branch_out(db: Session, b: Branch, current: uuid.UUID) -> dict:
    users = db.scalar(select(func.count()).select_from(User).where(User.branch_id == b.id, User.is_active.is_(True)))
    return {"id": str(b.id), "name": b.name, "address": b.address, "phone": b.phone, "is_default": b.is_default, "is_active": b.is_active,
            "users_count": users, "current": b.id == current}


@router.get("/branches", tags=[TAG], response_model=List[BranchOut], summary="Filiallar",
            description="`branches:all` (administrator): hamma filial (faolsizlari `branches:manage` bilan); boshqalar: faqat o'z filiali. `current`: faol filial.")
def list_branches(include_inactive: bool = False, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    stmt = select(Branch).order_by(Branch.is_default.desc(), Branch.name)
    if "branches:all" not in user.permissions:
        stmt = stmt.where(Branch.id == user.branch_id)
    elif not (include_inactive and "branches:manage" in user.permissions):
        stmt = stmt.where(Branch.is_active.is_(True))
    return [branch_out(db, b, user.branch_id) for b in db.scalars(stmt)]


@router.post("/branches", tags=[TAG], response_model=BranchOut, status_code=201, summary="Filial qo'shish",
             description="Yangi filial uchun klinika sozlamalari (nom, valyuta, til, chegirma limiti ...) asosiy filialdan nusxalanadi. "
                         "Bemorlar bazasi hamma filialga umumiy; jadval, kassa, ombor va hisobotlar filial bo'yicha.")
def create_branch(data: BranchIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("branches:manage"))):
    branch = Branch(name=data.name.strip(), address=(data.address or "").strip() or None, phone=(data.phone or "").strip() or None,
                    is_default=False, is_active=True, created_by=user.id)
    db.add(branch)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday nomli filial allaqachon mavjud")
    base = db.scalar(select(ClinicSettings).join(Branch, ClinicSettings.branch_id == Branch.id).where(Branch.is_default.is_(True)))
    db.add(ClinicSettings(
        branch_id=branch.id, clinic_name=base.clinic_name if base else "Digital Clinic", address=branch.address, phone=branch.phone,
        email=base.email if base else None, currency=base.currency if base else "UZS", timezone=base.timezone if base else "Asia/Tashkent",
        language=base.language if base else "uz", discount_limit_percent=base.discount_limit_percent if base else 10,
        commission_base=base.commission_base if base else "NetOfVat", quiet_start_hour=base.quiet_start_hour if base else 21,
        quiet_end_hour=base.quiet_end_hour if base else 8, created_by=user.id))
    audit.record(db, user, request, "create", "branch", branch.id, {"name": branch.name})
    db.commit()
    return branch_out(db, branch, user.branch_id)


@router.put("/branches/{branch_id}", tags=[TAG], response_model=BranchOut, summary="Filialni o'zgartirish",
            description="Filial o'chirilmaydi, faolsizlantiriladi. Asosiy filialni, faol xodimi yoki ombor qoldig'i bor filialni faolsizlantirib bo'lmaydi (409).")
def update_branch(branch_id: uuid.UUID, data: BranchUpdate, request: Request, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require("branches:manage"))):
    branch = db.get(Branch, branch_id)
    if not branch:
        raise HTTPException(404, "Filial topilmadi")
    if data.is_active is False and branch.is_active:
        if branch.is_default:
            raise HTTPException(409, "Asosiy filialni faolsizlantirib bo'lmaydi")
        if branch.id == user.branch_id:
            raise HTTPException(409, "Faol filialni faolsizlantirib bo'lmaydi: avval boshqa filialga o'ting")
        if db.scalar(select(func.count()).select_from(User).where(User.branch_id == branch.id, User.is_active.is_(True))):
            raise HTTPException(409, "Filialda faol xodimlar bor: avval ularni boshqa filialga biriktiring")
        if db.scalar(select(func.count()).select_from(StockBatch).where(StockBatch.branch_id == branch.id, StockBatch.qty_remaining > 0)):
            raise HTTPException(409, "Filial omborida qoldiq bor: avval boshqa filialga ko'chiring yoki hisobdan chiqaring")
    changes = {}
    for key, value in data.model_dump(exclude_unset=True).items():
        if key in ("name", "is_active") and value is None:
            continue
        if isinstance(value, str):
            value = value.strip() or None
        if getattr(branch, key) != value:
            changes[key] = {"from": getattr(branch, key), "to": value}
            setattr(branch, key, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday nomli filial allaqachon mavjud")
    if changes:
        audit.record(db, user, request, "update", "branch", branch.id, {"changes": changes})
    db.commit()
    return branch_out(db, branch, user.branch_id)
