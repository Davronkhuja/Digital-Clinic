# ruff: noqa: E501
"""Ombor: kirim, qoldiq, partiyalar. Qoldiq filial bo'yicha partiyalarda; harakatlar jurnali (`stock_movements`) faqat qo'shiladi."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Service, ServiceMaterial, StockBatch, StockItem, StockMovement, StockReceipt
from app.schemas.enums import StockMovementKind
from app.services.money import q2
from app.services.periods import clinic_today

ZERO = Decimal("0.000")
EXPIRY_WARN_DAYS = 30


def receive(db: Session, user, *, supplier: str | None, doc_no: str | None, received_on: date | None, notes: str | None, lines: list) -> StockReceipt:
    """Kirim hujjati: har qator alohida partiya va `Receipt` harakati. Muddati o'tgan tovar qabul qilinmaydi."""
    today = clinic_today()
    on = received_on or today
    if on > today:
        raise HTTPException(422, "Kirim sanasi kelajakda bo'lishi mumkin emas")
    receipt = StockReceipt(supplier=(supplier or "").strip() or None, doc_no=(doc_no or "").strip() or None, received_on=on,
                           notes=(notes or "").strip() or None, branch_id=user.branch_id, created_by=user.id)
    db.add(receipt)
    db.flush()
    for n, line in enumerate(lines, 1):
        item = db.get(StockItem, line.item_id)
        if not item or not item.is_active:
            raise HTTPException(422, f"{n}-qator: material topilmadi yoki faol emas")
        if line.expires_on and line.expires_on < today:
            raise HTTPException(422, f"{n}-qator ({item.name}): yaroqlilik muddati o'tgan, qabul qilib bo'lmaydi")
        batch = StockBatch(item_id=item.id, receipt_id=receipt.id, batch_no=line.batch_no, expires_on=line.expires_on, received_on=on,
                           unit_cost=q2(line.unit_cost), qty_received=line.qty, qty_remaining=line.qty, branch_id=user.branch_id,
                           created_by=user.id)
        db.add(batch)
        db.flush()
        db.add(StockMovement(item_id=item.id, batch_id=batch.id, kind=StockMovementKind.receipt, qty=line.qty, unit_cost=batch.unit_cost,
                             ref_type="receipt", ref_id=receipt.id, reason=receipt.supplier, branch_id=user.branch_id, created_by=user.id))
    return receipt


def receipt_out(db: Session, receipt: StockReceipt) -> dict:
    rows = db.execute(select(StockBatch, StockItem).join(StockItem, StockBatch.item_id == StockItem.id)
                      .where(StockBatch.receipt_id == receipt.id).order_by(StockItem.name, StockBatch.batch_no)).all()
    lines = [{"batch_id": str(b.id), "item_id": str(i.id), "item": i.name, "unit": i.unit, "batch_no": b.batch_no, "expires_on": b.expires_on,
              "qty": b.qty_received, "unit_cost": b.unit_cost, "amount": q2(b.qty_received * b.unit_cost)} for b, i in rows]
    return {"id": str(receipt.id), "supplier": receipt.supplier, "doc_no": receipt.doc_no, "received_on": receipt.received_on,
            "notes": receipt.notes, "created_at": receipt.created_at.isoformat(), "total": sum((ln["amount"] for ln in lines), q2(0)),
            "lines": lines}


def stock_rows(db: Session, branch_id: uuid.UUID, *, item_id: uuid.UUID | None = None, search: str | None = None,
               low_only: bool = False, include_inactive: bool = False) -> list[dict]:
    """Material bo'yicha qoldiq (filialda). Qoldig'i yo'q faol materiallar ham chiqadi (minimal qoldiq ogohlantirishi uchun)."""
    today = clinic_today()
    live = (StockBatch.expires_on.is_(None)) | (StockBatch.expires_on >= today)
    qty = func.coalesce(func.sum(StockBatch.qty_remaining), 0)
    usable = func.coalesce(func.sum(case((live, StockBatch.qty_remaining), else_=0)), 0)
    value = func.coalesce(func.sum(StockBatch.qty_remaining * StockBatch.unit_cost), 0)
    stmt = (select(StockItem, qty, usable, value)
            .outerjoin(StockBatch, (StockBatch.item_id == StockItem.id) & (StockBatch.branch_id == branch_id))
            .group_by(StockItem.id).order_by(StockItem.name))
    if not include_inactive:
        stmt = stmt.where(StockItem.is_active.is_(True))
    if item_id:
        stmt = stmt.where(StockItem.id == item_id)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(StockItem.name.ilike(like) | StockItem.sku.ilike(like))
    out = []
    for item, total, ok, val in db.execute(stmt).all():
        low = item.min_qty > 0 and Decimal(ok) < item.min_qty
        if low_only and not low:
            continue
        out.append({"item_id": str(item.id), "name": item.name, "kind": item.kind, "unit": item.unit, "sku": item.sku, "min_qty": item.min_qty,
                    "qty": Decimal(total), "usable_qty": Decimal(ok), "expired_qty": Decimal(total) - Decimal(ok), "value": q2(val), "low": low})
    return out


def batch_rows(db: Session, branch_id: uuid.UUID, *, item_id: uuid.UUID | None = None, include_empty: bool = False,
               expiring_within: int | None = None) -> list[dict]:
    today = clinic_today()
    stmt = (select(StockBatch, StockItem).join(StockItem, StockBatch.item_id == StockItem.id).where(StockBatch.branch_id == branch_id)
            .order_by(StockItem.name, StockBatch.expires_on.asc().nulls_last(), StockBatch.created_at))
    if item_id:
        stmt = stmt.where(StockBatch.item_id == item_id)
    if not include_empty:
        stmt = stmt.where(StockBatch.qty_remaining > 0)
    if expiring_within is not None:
        stmt = stmt.where(StockBatch.expires_on.is_not(None), StockBatch.expires_on <= today + timedelta(days=expiring_within))
    out = []
    for b, i in db.execute(stmt).all():
        left = (b.expires_on - today).days if b.expires_on else None
        out.append({"id": str(b.id), "item_id": str(i.id), "item": i.name, "unit": i.unit, "batch_no": b.batch_no, "expires_on": b.expires_on,
                    "days_left": left, "expired": left is not None and left < 0, "received_on": b.received_on, "unit_cost": b.unit_cost,
                    "qty_received": b.qty_received, "qty_remaining": b.qty_remaining, "receipt_id": str(b.receipt_id) if b.receipt_id else None})
    return out


class Allocation:
    """FEFO bo'yicha bitta partiyadan olingan miqdor."""

    def __init__(self, batch: StockBatch, qty: Decimal):
        self.batch, self.qty = batch, qty

    @property
    def cost(self) -> Decimal:
        return q2(self.qty * self.batch.unit_cost)


def fefo_allocate(db: Session, branch_id: uuid.UUID, item_id: uuid.UUID, qty: Decimal, *, for_update: bool = True) -> list[Allocation]:
    """Birinchi tugaydigan birinchi chiqadi: yaroqli (muddati o'tmagan yoki muddatsiz) partiyalar muddati bo'yicha, muddatsizlar oxirida;
    muddati teng bo'lsa avval kirgani. Muddati o'tgan partiyalar ishlatilmaydi. Yetmasa 409 (hech narsa o'zgarmaydi)."""
    today = clinic_today()
    stmt = (select(StockBatch).where(StockBatch.branch_id == branch_id, StockBatch.item_id == item_id, StockBatch.qty_remaining > 0,
                                     (StockBatch.expires_on.is_(None)) | (StockBatch.expires_on >= today))
            .order_by(StockBatch.expires_on.asc().nulls_last(), StockBatch.received_on, StockBatch.created_at, StockBatch.id))
    if for_update:
        stmt = stmt.with_for_update()          # parallel chiqimlar bir partiyani ikki marta olmasin
    left, out = qty, []
    for batch in db.scalars(stmt):
        take = min(batch.qty_remaining, left)
        out.append(Allocation(batch, take))
        left -= take
        if left <= 0:
            break
    if left > 0:
        have = qty - left
        expired = db.scalar(select(func.coalesce(func.sum(StockBatch.qty_remaining), 0)).where(
            StockBatch.branch_id == branch_id, StockBatch.item_id == item_id, StockBatch.expires_on < today))
        hint = f"; muddati o'tgan {Decimal(expired).normalize():f} bor (hisobdan chiqaring)" if expired else ""
        raise HTTPException(409, f"Qoldiq yetmaydi: kerak {qty.normalize():f}, yaroqli {have.normalize():f}{hint}")
    return out


def issue(db: Session, user, *, item_id: uuid.UUID, qty: Decimal, reason: str, kind: StockMovementKind = StockMovementKind.issue,
          ref_type: str | None = None, ref_id: uuid.UUID | None = None, branch_id: uuid.UUID | None = None) -> list[Allocation]:
    """FEFO bo'yicha chiqim: partiyalar kamayadi, har partiya uchun manfiy harakat yoziladi."""
    branch = branch_id or user.branch_id
    allocations = fefo_allocate(db, branch, item_id, qty)
    for a in allocations:
        a.batch.qty_remaining -= a.qty
        db.add(StockMovement(item_id=item_id, batch_id=a.batch.id, kind=kind, qty=-a.qty, unit_cost=a.batch.unit_cost, reason=reason[:300],
                             ref_type=ref_type, ref_id=ref_id, branch_id=branch, created_by=getattr(user, "id", None)))
    return allocations


def allocations_out(allocs: list[Allocation]) -> list[dict]:
    return [{"batch_id": str(a.batch.id), "batch_no": a.batch.batch_no, "expires_on": a.batch.expires_on, "qty": a.qty,
             "unit_cost": a.batch.unit_cost, "amount": a.cost} for a in allocs]


def alerts(db: Session, branch_id: uuid.UUID, days: int = EXPIRY_WARN_DAYS) -> dict:
    """Ogohlantirishlar: minimal qoldiqdan kam, `days` ichida muddati tugaydigan va muddati o'tgan (qoldig'i bor) partiyalar."""
    rows = batch_rows(db, branch_id, expiring_within=days)           # muddat bo'yicha: o'tganlar ham tepada
    return {"expiry_days": days, "low_stock": stock_rows(db, branch_id, low_only=True),
            "expiring": [r for r in rows if not r["expired"]], "expired": [r for r in rows if r["expired"]]}


def writeoff(db: Session, user, *, batch_id: uuid.UUID, qty: Decimal | None, reason: str) -> tuple[StockBatch, Decimal]:
    """Partiyadan hisobdan chiqarish (muddati o'tgan, singan, yo'qolgan): `Writeoff` harakati. Faqat o'z filialidagi partiya."""
    batch = db.scalar(select(StockBatch).where(StockBatch.id == batch_id).with_for_update())
    if not batch or batch.branch_id != user.branch_id:
        raise HTTPException(404, "Partiya topilmadi")
    take = batch.qty_remaining if qty is None else qty
    if batch.qty_remaining <= 0:
        raise HTTPException(409, "Partiyada qoldiq yo'q")
    if take > batch.qty_remaining:
        raise HTTPException(409, f"Qoldiq yetmaydi: partiyada {batch.qty_remaining.normalize():f}")
    batch.qty_remaining -= take
    db.add(StockMovement(item_id=batch.item_id, batch_id=batch.id, kind=StockMovementKind.writeoff, qty=-take, unit_cost=batch.unit_cost,
                         reason=reason[:300], ref_type="writeoff", branch_id=batch.branch_id, created_by=user.id))
    return batch, take


def unit_cost_basis(db: Session, branch_id: uuid.UUID, item_id: uuid.UUID) -> tuple[Decimal | None, str]:
    """Material birligi narxi (tannarx uchun): 1) ombordagi yaroqli qoldiqning o'rtacha tortilgan narxi ("stock");
    2) qoldiq bo'lmasa filialdagi oxirgi kirim narxi ("last_receipt"); 3) kirim hali yo'q: noma'lum ("unknown")."""
    today = clinic_today()
    live = (StockBatch.expires_on.is_(None)) | (StockBatch.expires_on >= today)
    qty, value = db.execute(select(func.coalesce(func.sum(StockBatch.qty_remaining), 0), func.coalesce(func.sum(StockBatch.qty_remaining * StockBatch.unit_cost), 0))
                            .where(StockBatch.branch_id == branch_id, StockBatch.item_id == item_id, StockBatch.qty_remaining > 0, live)).one()
    if Decimal(qty) > 0:
        return Decimal(value) / Decimal(qty), "stock"
    last = db.scalar(select(StockBatch.unit_cost).where(StockBatch.branch_id == branch_id, StockBatch.item_id == item_id)
                     .order_by(StockBatch.received_on.desc(), StockBatch.created_at.desc()).limit(1))
    return (last, "last_receipt") if last is not None else (None, "unknown")


def service_materials(db: Session, service_id: uuid.UUID) -> list[tuple[ServiceMaterial, StockItem]]:
    return db.execute(select(ServiceMaterial, StockItem).join(StockItem, ServiceMaterial.item_id == StockItem.id)
                      .where(ServiceMaterial.service_id == service_id).order_by(StockItem.name)).all()


def service_cost(db: Session, branch_id: uuid.UUID, service: Service) -> dict:
    """Xizmat tannarxi = sarf normasi x material narxi (avtomatik: ombor narxi o'zgarsa tannarx ham o'zgaradi). Foyda QQS'siz narxdan."""
    lines, total, missing = [], Decimal(0), []
    for m, item in service_materials(db, service.id):
        unit_cost, source = unit_cost_basis(db, branch_id, item.id)
        cost = q2(m.qty * unit_cost) if unit_cost is not None else None
        if cost is None:
            missing.append(item.name)
        else:
            total += m.qty * unit_cost
        lines.append({"item_id": str(item.id), "item": item.name, "unit": item.unit, "qty": m.qty,
                      "unit_cost": q2(unit_cost) if unit_cost is not None else None, "cost": cost, "source": source})
    cost_total = q2(total)
    net = q2(service.price * 100 / (100 + service.vat_percent)) if service.vat_percent is not None else service.price
    margin = q2(net - cost_total)
    return {"service_id": str(service.id), "service": service.name, "price": service.price, "vat_percent": service.vat_percent, "net_price": net,
            "cost": cost_total, "margin": margin, "margin_percent": float(round(margin * 100 / net, 1)) if net > 0 else None,
            "complete": not missing and bool(lines), "missing": missing, "materials": lines}
