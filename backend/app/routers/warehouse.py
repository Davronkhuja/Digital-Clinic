# ruff: noqa: E501
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Staff, StockBatch, StockItem, StockMovement, StockReceipt, User
from app.schemas import (
    AlertsOut,
    BatchOut,
    IssueIn,
    IssueOut,
    MovementOut,
    ReceiptIn,
    ReceiptOut,
    StockItemIn,
    StockItemOut,
    StockItemUpdate,
    StockRowOut,
    WriteoffIn,
)
from app.schemas.enums import StockKind, StockMovementKind
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
            description="Minimal qoldiqdan kam materiallar (yaroqli qoldiq bo'yicha), `days` (standart 30) ichida muddati tugaydigan "
                        "va muddati o'tgan partiyalar (qoldig'i bor).")
def alerts(days: int = Query(wh.EXPIRY_WARN_DAYS, ge=1, le=365), db: Session = Depends(get_db),
           user: CurrentUser = Depends(require("warehouse:read"))):
    return wh.alerts(db, user.branch_id, days)


@router.post("/warehouse/writeoffs", tags=[TAG], response_model=List[MovementOut], status_code=201, summary="Hisobdan chiqarish",
             description="Partiyani (yoki bir qismini) hisobdan chiqaradi: muddati o'tgan, singan, yo'qolgan. Sabab majburiy; `Writeoff` harakati, audit.")
def create_writeoff(data: WriteoffIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("warehouse:write"))):
    batch, qty = wh.writeoff(db, user, batch_id=data.batch_id, qty=data.qty, reason=data.reason)
    audit.record(db, user, request, "create", "stock_writeoff", batch.id, {"batch_no": batch.batch_no, "qty": str(qty), "reason": data.reason})
    db.commit()
    return movements(item_id=batch.item_id, kind=StockMovementKind.writeoff, limit=1, db=db, user=user)


@router.post("/warehouse/issues", tags=[TAG], response_model=IssueOut, summary="Chiqim (FEFO)",
             description="Birinchi tugaydigan partiyadan boshlab olinadi (muddatsizlar oxirida); muddati o'tgan partiyalar ishlatilmaydi. "
                         "Yaroqli qoldiq yetmasa 409 va hech narsa o'zgarmaydi. Har partiya uchun `Issue` harakati yoziladi.")
def create_issue(data: IssueIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("warehouse:write"))):
    item = db.get(StockItem, data.item_id)
    if not item or not item.is_active:
        raise HTTPException(422, "Material topilmadi yoki faol emas")
    allocs = wh.issue(db, user, item_id=item.id, qty=data.qty, reason=data.reason)
    audit.record(db, user, request, "create", "stock_issue", item.id, {"item": item.name, "qty": str(data.qty), "reason": data.reason,
                                                                    "batches": [a.batch.batch_no for a in allocs]})
    db.commit()
    return {"item_id": str(item.id), "item": item.name, "unit": item.unit, "qty": data.qty,
            "total_cost": sum((a.cost for a in allocs), wh.q2(0)), "allocations": wh.allocations_out(allocs)}


@router.get("/warehouse/movements", tags=[TAG], response_model=List[MovementOut], summary="Qoldiq harakatlari jurnali (shu filial)",
            description="Faqat qo'shiladi, o'zgarmaydi. Yangilari tepada.")
def movements(item_id: Optional[uuid.UUID] = None, kind: Optional[StockMovementKind] = None, limit: int = 100,
              db: Session = Depends(get_db), user: CurrentUser = Depends(require("warehouse:read"))):
    stmt = (select(StockMovement, StockItem, StockBatch, Staff.full_name)
            .join(StockItem, StockMovement.item_id == StockItem.id).join(StockBatch, StockMovement.batch_id == StockBatch.id)
            .outerjoin(User, StockMovement.created_by == User.id).outerjoin(Staff, User.staff_id == Staff.id)
            .where(StockMovement.branch_id == user.branch_id).order_by(StockMovement.created_at.desc(), StockMovement.id).limit(min(max(limit, 1), 500)))
    if item_id:
        stmt = stmt.where(StockMovement.item_id == item_id)
    if kind:
        stmt = stmt.where(StockMovement.kind == kind)
    return [{"id": str(m.id), "at": m.created_at.isoformat(), "kind": m.kind, "item_id": str(i.id), "item": i.name, "unit": i.unit,
             "batch_id": str(b.id), "batch_no": b.batch_no, "qty": m.qty, "unit_cost": m.unit_cost, "reason": m.reason, "ref_type": m.ref_type,
             "ref_id": str(m.ref_id) if m.ref_id else None, "by": by} for m, i, b, by in db.execute(stmt).all()]
