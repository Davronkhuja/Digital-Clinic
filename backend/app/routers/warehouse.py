import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import StockItem
from app.schemas import StockItemIn, StockItemOut, StockItemUpdate
from app.schemas.enums import StockKind
from app.services import audit

router = APIRouter()
TAG = "📦 Warehouse (ombor)"


def item_out(i: StockItem) -> dict:
    return {"id": str(i.id), "name": i.name, "kind": i.kind, "unit": i.unit, "sku": i.sku, "min_qty": i.min_qty,
            "is_active": i.is_active, "notes": i.notes}


def _conflict() -> HTTPException:
    return HTTPException(409, "Bunday nomli yoki SKU li material allaqachon mavjud")


@router.get("/warehouse/items", tags=[TAG], response_model=List[StockItemOut], summary="Dori va sarf materiallari katalogi")
def list_items(search: Optional[str] = None, kind: Optional[StockKind] = None, include_inactive: bool = False,
               db: Session = Depends(get_db), user: CurrentUser = Depends(require("warehouse:read"))):
    stmt = select(StockItem).order_by(StockItem.name)
    if not include_inactive:
        stmt = stmt.where(StockItem.is_active.is_(True))
    if kind:
        stmt = stmt.where(StockItem.kind == kind)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(StockItem.name.ilike(like) | StockItem.sku.ilike(like))
    return [item_out(i) for i in db.scalars(stmt)]


@router.post("/warehouse/items", tags=[TAG], response_model=StockItemOut, status_code=201, summary="Material qo'shish",
             description="Katalog hamma filialga umumiy; qoldiq filial bo'yicha partiyalarda. `min_qty`: shundan kam qolsa ogohlantirish.")
def create_item(data: StockItemIn, request: Request, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require("warehouse:write"))):
    item = StockItem(name=data.name.strip(), kind=data.kind, unit=data.unit.strip(), sku=data.sku, min_qty=data.min_qty,
                     is_active=data.is_active, notes=data.notes, created_by=user.id)
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _conflict()
    audit.record(db, user, request, "create", "stock_item", item.id, {"name": item.name, "kind": item.kind.value, "unit": item.unit})
    db.commit()
    return item_out(item)


@router.put("/warehouse/items/{item_id}", tags=[TAG], response_model=StockItemOut, summary="Materialni o'zgartirish",
            description="Material o'chirilmaydi, faolsizlantiriladi (`is_active=false`). Mavjud partiyalar va harakatlar saqlanadi.")
def update_item(item_id: uuid.UUID, data: StockItemUpdate, request: Request, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require("warehouse:write"))):
    item = db.get(StockItem, item_id)
    if not item:
        raise HTTPException(404, "Material topilmadi")
    changes = {}
    for key, value in data.model_dump(exclude_unset=True).items():
        if key in ("name", "kind", "unit", "min_qty", "is_active") and value is None:
            continue
        if key in ("name", "unit"):
            value = value.strip()
        old = getattr(item, key)
        if old != value:
            changes[key] = {"from": str(getattr(old, "value", old)), "to": str(getattr(value, "value", value))}
            setattr(item, key, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _conflict()
    if changes:
        audit.record(db, user, request, "update", "stock_item", item.id, {"changes": changes})
    db.commit()
    return item_out(item)
