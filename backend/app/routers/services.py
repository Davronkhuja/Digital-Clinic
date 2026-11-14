# ruff: noqa: E501
import uuid
from decimal import Decimal
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Branch, Service, ServiceBranchPrice, ServiceCategory
from app.schemas.common import Money
from app.schemas.services import ServiceCategoryIn, ServiceCategoryOut, ServiceIn, ServiceOut, ServiceUpdate
from app.services import audit

router = APIRouter()
TAG = "🏷 Services (narxnoma)"


def service_out(s: Service, category: str | None, branch_price=None) -> dict:
    return {"id": str(s.id), "name": s.name, "category_id": str(s.category_id) if s.category_id else None, "category": category,
            "price": s.price, "branch_price": branch_price, "effective_price": s.price if branch_price is None else branch_price,
            "mxik": s.mxik, "package_code": s.package_code, "vat_percent": s.vat_percent,
            "is_active": s.is_active, "sellable": s.sellable, "missing": s.missing_fields}


def _category_id(db: Session, value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        cid = uuid.UUID(value)
    except ValueError:
        raise HTTPException(422, "category_id noto'g'ri")
    if not db.get(ServiceCategory, cid):
        raise HTTPException(422, "Kategoriya topilmadi")
    return cid


def _overrides(db: Session, branch_id: uuid.UUID) -> dict:
    return {r.service_id: r.price for r in db.scalars(select(ServiceBranchPrice).where(ServiceBranchPrice.branch_id == branch_id))}


def _load(db: Session, service_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
    row = db.execute(select(Service, ServiceCategory.name).outerjoin(ServiceCategory, Service.category_id == ServiceCategory.id)
                     .where(Service.id == service_id)).first()
    if not row:
        raise HTTPException(404, "Xizmat topilmadi")
    bp = db.scalar(select(ServiceBranchPrice.price).where(ServiceBranchPrice.service_id == service_id,
                                                          ServiceBranchPrice.branch_id == branch_id)) if branch_id else None
    return service_out(*row, bp)


@router.get("/services", tags=[TAG], response_model=List[ServiceOut], summary="Narxnoma",
            description="`sellable=true`: faqat sotiladigan (faol, MXIK/package_code/QQS to'liq) xizmatlar.")
def list_services(search: Optional[str] = None, category_id: Optional[uuid.UUID] = None, sellable: Optional[bool] = None,
                  include_inactive: bool = False, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require("services:read"))):
    stmt = (select(Service, ServiceCategory.name).outerjoin(ServiceCategory, Service.category_id == ServiceCategory.id)
            .order_by(ServiceCategory.name, Service.name))
    if not include_inactive:
        stmt = stmt.where(Service.is_active.is_(True))
    if search:
        stmt = stmt.where(Service.name.ilike(f"%{search.strip()}%"))
    if category_id:
        stmt = stmt.where(Service.category_id == category_id)
    over = _overrides(db, user.branch_id)
    rows = [service_out(s, c, over.get(s.id)) for s, c in db.execute(stmt).all()]
    if sellable is not None:
        rows = [r for r in rows if r["sellable"] == sellable]
    return rows


@router.post("/services", tags=[TAG], response_model=ServiceOut, status_code=201, summary="Xizmat qo'shish",
             description="MXIK (17 raqam), package_code va QQS bo'lmasa xizmat saqlanadi, lekin sotib bo'lmaydi (`sellable=false`).")
def create_service(data: ServiceIn, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("services:write"))):
    s = Service(name=data.name.strip(), category_id=_category_id(db, data.category_id), price=data.price, mxik=data.mxik,
                package_code=data.package_code, vat_percent=data.vat_percent, is_active=data.is_active, created_by=user.id)
    db.add(s)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday nomli xizmat allaqachon mavjud")
    audit.record(db, user, request, "create", "service", s.id, {"name": s.name, "price": str(s.price)})
    db.commit()
    return _load(db, s.id, user.branch_id)


@router.put("/services/{service_id}", tags=[TAG], response_model=ServiceOut, summary="Xizmatni o'zgartirish",
            description="Yozilgan hisob-fakturalarga ta'sir qilmaydi (narx va soliq maydonlari nusxalangan). Xizmat o'chirilmaydi.")
def update_service(service_id: uuid.UUID, data: ServiceUpdate, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require("services:write"))):
    s = db.get(Service, service_id)
    if not s:
        raise HTTPException(404, "Xizmat topilmadi")
    fields = data.model_dump(exclude_unset=True)
    changes = {}
    for key, value in fields.items():
        if key in ("name", "price", "is_active") and value is None:
            continue
        if key == "category_id":
            value = _category_id(db, value)
        if key == "name":
            value = value.strip()
        old = getattr(s, key)
        if old != value:
            changes[key] = {"from": str(old), "to": str(value)}
            setattr(s, key, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday nomli xizmat allaqachon mavjud")
    if changes:
        audit.record(db, user, request, "update", "service", s.id, {"changes": changes})
    db.commit()
    return _load(db, s.id, user.branch_id)


@router.get("/service-categories", tags=[TAG], response_model=List[ServiceCategoryOut], summary="Xizmat kategoriyalari")
def list_categories(include_inactive: bool = False, db: Session = Depends(get_db), user: CurrentUser = Depends(require("services:read"))):
    stmt = select(ServiceCategory).order_by(ServiceCategory.name)
    if not include_inactive:
        stmt = stmt.where(ServiceCategory.is_active.is_(True))
    return [{"id": str(c.id), "name": c.name, "is_active": c.is_active} for c in db.scalars(stmt)]


@router.post("/service-categories", tags=[TAG], response_model=ServiceCategoryOut, status_code=201, summary="Kategoriya qo'shish")
def create_category(data: ServiceCategoryIn, db: Session = Depends(get_db), user: CurrentUser = Depends(require("services:write"))):
    c = ServiceCategory(name=data.name.strip(), is_active=data.is_active, created_by=user.id)
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday kategoriya allaqachon mavjud")
    return {"id": str(c.id), "name": c.name, "is_active": c.is_active}


@router.put("/service-categories/{category_id}", tags=[TAG], response_model=ServiceCategoryOut, summary="Kategoriyani o'zgartirish")
def update_category(category_id: uuid.UUID, data: ServiceCategoryIn, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require("services:write"))):
    c = db.get(ServiceCategory, category_id)
    if not c:
        raise HTTPException(404, "Kategoriya topilmadi")
    c.name, c.is_active = data.name.strip(), data.is_active
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday kategoriya allaqachon mavjud")
    return {"id": str(c.id), "name": c.name, "is_active": c.is_active}


class BranchPriceOut(BaseModel):
    branch_id: str
    branch: str
    price: Money


class BranchPriceIn(BaseModel):
    price: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2, description="Faol filialdagi narx (QQS bilan)")]


@router.get("/services/{service_id}/branch-prices", tags=[TAG], response_model=List[BranchPriceOut], summary="Xizmatning filial narxlari",
            description="Asosiy narxdan farqli narx belgilangan filiallar. Narxi belgilanmagan filialda asosiy narx amal qiladi.")
def list_branch_prices(service_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(require("services:read"))):
    if not db.get(Service, service_id):
        raise HTTPException(404, "Xizmat topilmadi")
    rows = db.execute(select(ServiceBranchPrice, Branch.name).join(Branch, ServiceBranchPrice.branch_id == Branch.id)
                      .where(ServiceBranchPrice.service_id == service_id).order_by(Branch.name)).all()
    return [{"branch_id": str(p.branch_id), "branch": name, "price": p.price} for p, name in rows]


@router.put("/services/{service_id}/branch-price", tags=[TAG], response_model=ServiceOut, summary="Faol filial uchun narx belgilash",
            description="Xizmatning shu (faol) filialdagi narxi; qolgan filiallar va asosiy narx o'zgarmaydi. Yangi hisob-fakturalarga ta'sir qiladi "
                        "(yozilganlari o'zgarmaydi). `services:write`, audit.")
def put_branch_price(service_id: uuid.UUID, data: BranchPriceIn, request: Request, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require("services:write"))):
    if not db.get(Service, service_id):
        raise HTTPException(404, "Xizmat topilmadi")
    row = db.scalar(select(ServiceBranchPrice).where(ServiceBranchPrice.service_id == service_id, ServiceBranchPrice.branch_id == user.branch_id))
    old = row.price if row else None
    if row:
        row.price = data.price
    else:
        db.add(ServiceBranchPrice(service_id=service_id, branch_id=user.branch_id, price=data.price, created_by=user.id))
    audit.record(db, user, request, "update", "service_branch_price", service_id,
                 {"branch_id": str(user.branch_id), "price": {"from": str(old) if old is not None else None, "to": str(data.price)}})
    db.commit()
    return _load(db, service_id, user.branch_id)


@router.delete("/services/{service_id}/branch-price", tags=[TAG], response_model=ServiceOut, summary="Faol filial narxini olib tashlash (asosiy narxga qaytish)")
def delete_branch_price(service_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("services:write"))):
    row = db.scalar(select(ServiceBranchPrice).where(ServiceBranchPrice.service_id == service_id, ServiceBranchPrice.branch_id == user.branch_id))
    if not row:
        raise HTTPException(404, "Bu filialda alohida narx belgilanmagan")
    audit.record(db, user, request, "update", "service_branch_price", service_id,
                 {"branch_id": str(user.branch_id), "price": {"from": str(row.price), "to": None}})
    db.delete(row)
    db.commit()
    return _load(db, service_id, user.branch_id)
