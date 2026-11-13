# ruff: noqa: E501
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import StockItem, StockReceipt
from app.schemas import AlertsOut, BatchOut, ReceiptIn, ReceiptOut, StockItemIn, StockItemOut, StockItemUpdate, StockRowOut
from app.schemas.enums import StockKind
from app.services import audit
from app.services import warehouse as wh

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


@router.post("/warehouse/receipts", tags=[TAG], response_model=ReceiptOut, status_code=201, summary="Kirim hujjati",
             description="Har qator alohida partiya (partiya raqami, yaroqlilik muddati, kirim narxi) va `Receipt` harakati. "
                         "Muddati o'tgan tovar va kelajak sanasi rad etiladi (422). Hujjat o'zgarmaydi va o'chirilmaydi.")
def create_receipt(data: ReceiptIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("warehouse:write"))):
    receipt = wh.receive(db, user, supplier=data.supplier, doc_no=data.doc_no, received_on=data.received_on, notes=data.notes, lines=data.lines)
    audit.record(db, user, request, "create", "stock_receipt", receipt.id,
                 {"supplier": receipt.supplier, "doc_no": receipt.doc_no, "lines": len(data.lines)})
    db.commit()
    return wh.receipt_out(db, receipt)


@router.get("/warehouse/receipts", tags=[TAG], response_model=List[ReceiptOut], summary="Kirim hujjatlari (shu filial)")
def list_receipts(limit: int = 50, db: Session = Depends(get_db), user: CurrentUser = Depends(require("warehouse:read"))):
    rows = db.scalars(select(StockReceipt).where(StockReceipt.branch_id == user.branch_id)
                      .order_by(StockReceipt.received_on.desc(), StockReceipt.created_at.desc()).limit(min(max(limit, 1), 200)))
    return [wh.receipt_out(db, r) for r in rows]


@router.get("/warehouse/receipts/{receipt_id}", tags=[TAG], response_model=ReceiptOut, summary="Bitta kirim hujjati")
def get_receipt(receipt_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(require("warehouse:read"))):
    receipt = db.get(StockReceipt, receipt_id)
    if not receipt or receipt.branch_id != user.branch_id:
        raise HTTPException(404, "Kirim hujjati topilmadi")
    return wh.receipt_out(db, receipt)


@router.get("/warehouse/stock", tags=[TAG], response_model=List[StockRowOut], summary="Qoldiq (material bo'yicha, shu filial)",
            description="`usable_qty`: muddati o'tmagan qoldiq; `low`: yaroqli qoldiq `min_qty` dan kam. Qoldig'i yo'q faol materiallar ham chiqadi.")
def stock(search: Optional[str] = None, item_id: Optional[uuid.UUID] = None, low_only: bool = False, include_inactive: bool = False,
          db: Session = Depends(get_db), user: CurrentUser = Depends(require("warehouse:read"))):
    return wh.stock_rows(db, user.branch_id, item_id=item_id, search=search, low_only=low_only, include_inactive=include_inactive)


@router.get("/warehouse/batches", tags=[TAG], response_model=List[BatchOut], summary="Partiyalar (shu filial)",
            description="Yaroqlilik muddati bo'yicha (birinchi tugaydigani tepada). Standart: faqat qoldig'i bor partiyalar.")
def batches(item_id: Optional[uuid.UUID] = None, include_empty: bool = False, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require("warehouse:read"))):
    return wh.batch_rows(db, user.branch_id, item_id=item_id, include_empty=include_empty)


@router.get("/warehouse/alerts", tags=[TAG], response_model=AlertsOut, summary="Ogohlantirishlar",
            description="Minimal qoldiqdan kam materiallar (yaroqli qoldiq bo'yicha).")
def alerts(db: Session = Depends(get_db), user: CurrentUser = Depends(require("warehouse:read"))):
    return {"low_stock": wh.stock_rows(db, user.branch_id, low_only=True)}
