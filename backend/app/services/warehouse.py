# ruff: noqa: E501
"""Ombor: kirim, qoldiq, partiyalar. Qoldiq filial bo'yicha partiyalarda; harakatlar jurnali (`stock_movements`) faqat qo'shiladi."""
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import (
    Branch,
    Invoice,
    InvoiceLine,
    Service,
    ServiceMaterial,
    StockBatch,
    StockItem,
    StockMovement,
    StockReceipt,
    StockShortage,
    StockTransfer,
    StockTransferLine,
)
from app.models.warehouse import stock_transfer_number_seq
from app.schemas.enums import InvoiceStatus, StockMovementKind, TransferStatus
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


def fefo_allocate(db: Session, branch_id: uuid.UUID, item_id: uuid.UUID, qty: Decimal, *, for_update: bool = True,
                  partial: bool = False) -> list[Allocation]:
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
    if left > 0 and partial:       # bor qadarini olamiz (to'lov to'xtamasligi uchun); yetmagani chaqiruvchida hisoblanadi
        return out
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
    return {"expiry_days": days, "low_stock": stock_rows(db, branch_id, low_only=True), "shortages": open_shortages(db, branch_id),
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


def perform_line(db: Session, inv: Invoice, line: InvoiceLine, user_id: uuid.UUID | None) -> dict:
    """Xizmat qatori bajarildi: norma x miqdor FEFO bo'yicha ombordan yoziladi (`Consumption`, havola: qator). Bir marta.
    Qoldiq manfiyga tushmaydi: yetmagan miqdor `stock_shortages` ga yoziladi (ombor mas'uliga ogohlantirish)."""
    if line.performed_at is not None:
        return {"consumed": 0, "shortages": 0}
    shortages = consumed = 0
    for norm in db.scalars(select(ServiceMaterial).where(ServiceMaterial.service_id == line.service_id).order_by(ServiceMaterial.item_id)):
        need = norm.qty * line.quantity
        allocs = fefo_allocate(db, inv.branch_id, norm.item_id, need, partial=True)
        for a in allocs:
            a.batch.qty_remaining -= a.qty
            db.add(StockMovement(item_id=norm.item_id, batch_id=a.batch.id, kind=StockMovementKind.consumption, qty=-a.qty, unit_cost=a.batch.unit_cost,
                                 reason=f"Hisob-faktura {inv.number}", ref_type="invoice_line", ref_id=line.id, branch_id=inv.branch_id,
                                 created_by=user_id))
        got = sum((a.qty for a in allocs), Decimal(0))
        consumed += 1 if got else 0
        if need - got > 0:
            db.add(StockShortage(invoice_id=inv.id, invoice_line_id=line.id, item_id=norm.item_id, qty_missing=need - got, branch_id=inv.branch_id,
                                 created_by=user_id))
            shortages += 1
    line.performed_at, line.performed_by = datetime.now(UTC), user_id
    return {"consumed": consumed, "shortages": shortages}


def unperform_line(db: Session, inv: Invoice, line: InvoiceLine, user_id: uuid.UUID | None) -> None:
    """Bajarildi belgisini qaytarish (xato belgilangan): yozilgan sarf o'z partiyalariga qaytadi (`Return`), ochiq yetishmovchilik yopiladi."""
    moves = db.scalars(select(StockMovement).where(StockMovement.ref_type == "invoice_line", StockMovement.ref_id == line.id,
                                                   StockMovement.kind == StockMovementKind.consumption))
    for m in moves:
        batch = db.scalar(select(StockBatch).where(StockBatch.id == m.batch_id).with_for_update())
        batch.qty_remaining += -m.qty
        db.add(StockMovement(item_id=m.item_id, batch_id=batch.id, kind=StockMovementKind.return_, qty=-m.qty, unit_cost=batch.unit_cost,
                             reason=f"Hisob-faktura {inv.number}: bajarilmagan deb qaytarildi", ref_type="invoice_line", ref_id=line.id,
                             branch_id=m.branch_id, created_by=user_id))
    for sh in db.scalars(select(StockShortage).where(StockShortage.invoice_line_id == line.id, StockShortage.resolved_at.is_(None))):
        sh.resolved_at = datetime.now(UTC)
    line.performed_at = line.performed_by = None


def perform_invoice(db: Session, inv: Invoice, user_id: uuid.UUID | None) -> int:
    """Hisob-fakturaning hamma bajarilmagan qatorini bajarilgan deb belgilaydi (qabul `Completed` bo'lganda)."""
    n = 0
    for line in db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id, InvoiceLine.performed_at.is_(None)).order_by(InvoiceLine.position)):
        perform_line(db, inv, line, user_id)
        n += 1
    return n


def perform_for_appointment(db: Session, appointment_id: uuid.UUID, user_id: uuid.UUID | None) -> int:
    """Qabul yakunlanganda unga bog'langan (chiqarilgan, bekor qilinmagan) hisob-fakturalar xizmatlari bajarilgan hisoblanadi."""
    total = 0
    for inv in db.scalars(select(Invoice).where(Invoice.appointment_id == appointment_id, Invoice.status.notin_([InvoiceStatus.draft, InvoiceStatus.cancelled]))):
        total += perform_invoice(db, inv, user_id)
    return total


def open_shortages(db: Session, branch_id: uuid.UUID) -> list[dict]:
    rows = db.execute(select(StockShortage, StockItem, Invoice.number).join(StockItem, StockShortage.item_id == StockItem.id)
                      .join(Invoice, StockShortage.invoice_id == Invoice.id)
                      .where(StockShortage.branch_id == branch_id, StockShortage.resolved_at.is_(None)).order_by(StockShortage.created_at)).all()
    return [{"id": str(sh.id), "invoice_id": str(sh.invoice_id), "invoice_number": number, "item_id": str(i.id), "item": i.name, "unit": i.unit,
             "qty_missing": sh.qty_missing, "created_at": sh.created_at.isoformat()} for sh, i, number in rows]


def resolve_shortage(db: Session, user, shortage_id: uuid.UUID) -> StockShortage:
    """Kirimdan keyin yetmagan miqdorni FEFO bo'yicha yozadi (hammasi yoki 409, qisman emas)."""
    sh = db.scalar(select(StockShortage).where(StockShortage.id == shortage_id).with_for_update())
    if not sh or sh.branch_id != user.branch_id:
        raise HTTPException(404, "Yetishmovchilik topilmadi")
    if sh.resolved_at is not None:
        raise HTTPException(409, "Yetishmovchilik allaqachon hal qilingan")
    inv = db.get(Invoice, sh.invoice_id)
    allocs = fefo_allocate(db, sh.branch_id, sh.item_id, sh.qty_missing)
    for a in allocs:
        a.batch.qty_remaining -= a.qty
        db.add(StockMovement(item_id=sh.item_id, batch_id=a.batch.id, kind=StockMovementKind.consumption, qty=-a.qty, unit_cost=a.batch.unit_cost,
                             reason=f"Hisob-faktura {inv.number} (kechiktirilgan)", ref_type="invoice_line" if sh.invoice_line_id else "invoice",
                             ref_id=sh.invoice_line_id or inv.id, branch_id=sh.branch_id,
                             created_by=user.id))
    sh.resolved_at = datetime.now(UTC)
    return sh


# ---------- Filiallar orasida ko'chirish ----------

def send_transfer(db: Session, user, *, to_branch_id: uuid.UUID, notes: str | None, lines: list) -> StockTransfer:
    """Hujjatni yuboradi: manba (faol) filial qoldig'i FEFO bo'yicha darhol kamayadi (`TransferOut`); yo'lda turadi."""
    if to_branch_id == user.branch_id:
        raise HTTPException(422, "Bir filialning o'ziga ko'chirib bo'lmaydi")
    target = db.get(Branch, to_branch_id)
    if not target or not target.is_active:
        raise HTTPException(422, "Qabul qiluvchi filial topilmadi yoki faol emas")
    need: dict[uuid.UUID, Decimal] = {}
    for ln in lines:
        need[ln.item_id] = need.get(ln.item_id, Decimal(0)) + ln.qty
    transfer = StockTransfer(number=f"TR-{db.scalar(select(stock_transfer_number_seq.next_value())):06d}", from_branch_id=user.branch_id,
                             to_branch_id=target.id, status=TransferStatus.sent, notes=(notes or "").strip() or None,
                             sent_at=datetime.now(UTC), created_by=user.id)
    db.add(transfer)
    db.flush()
    for item_id, qty in sorted(need.items(), key=lambda kv: str(kv[0])):            # qulflash tartibi barqaror
        item = db.get(StockItem, item_id)
        if not item or not item.is_active:
            raise HTTPException(422, "Material topilmadi yoki faol emas")
        for a in fefo_allocate(db, user.branch_id, item_id, qty):
            a.batch.qty_remaining -= a.qty
            db.add(StockMovement(item_id=item_id, batch_id=a.batch.id, kind=StockMovementKind.transfer_out, qty=-a.qty, unit_cost=a.batch.unit_cost,
                                 reason=f"{transfer.number} -> {target.name}", ref_type="transfer", ref_id=transfer.id, branch_id=user.branch_id,
                                 created_by=user.id))
            db.add(StockTransferLine(transfer_id=transfer.id, item_id=item_id, source_batch_id=a.batch.id, batch_no=a.batch.batch_no,
                                     expires_on=a.batch.expires_on, unit_cost=a.batch.unit_cost, qty=a.qty, created_by=user.id))
    return transfer


def _locked_transfer(db: Session, user, transfer_id: uuid.UUID) -> StockTransfer:
    t = db.scalar(select(StockTransfer).where(StockTransfer.id == transfer_id).with_for_update())
    if not t or user.branch_id not in (t.from_branch_id, t.to_branch_id):
        raise HTTPException(404, "Ko'chirish hujjati topilmadi")
    if t.status != TransferStatus.sent:
        raise HTTPException(409, f"Hujjat holati {t.status.value}: o'zgartirib bo'lmaydi")
    return t


def receive_transfer(db: Session, user, transfer_id: uuid.UUID) -> StockTransfer:
    """Qabul qiluvchi filial qabul qiladi: shu filialda xuddi shu partiya raqami, muddati va narxi bilan partiya ochiladi (`TransferIn`)."""
    t = _locked_transfer(db, user, transfer_id)
    if user.branch_id != t.to_branch_id:
        raise HTTPException(403, "Faqat qabul qiluvchi filial qabul qila oladi")
    today = clinic_today()
    for line in db.scalars(select(StockTransferLine).where(StockTransferLine.transfer_id == t.id).order_by(StockTransferLine.created_at, StockTransferLine.id)):
        batch = StockBatch(item_id=line.item_id, receipt_id=None, batch_no=line.batch_no, expires_on=line.expires_on, received_on=today,
                           unit_cost=line.unit_cost, qty_received=line.qty, qty_remaining=line.qty, branch_id=t.to_branch_id, created_by=user.id)
        db.add(batch)
        db.flush()
        line.dest_batch_id = batch.id
        db.add(StockMovement(item_id=line.item_id, batch_id=batch.id, kind=StockMovementKind.transfer_in, qty=line.qty, unit_cost=line.unit_cost,
                             reason=t.number, ref_type="transfer", ref_id=t.id, branch_id=t.to_branch_id, created_by=user.id))
    t.status, t.received_at, t.received_by = TransferStatus.received, datetime.now(UTC), user.id
    return t


def cancel_transfer(db: Session, user, transfer_id: uuid.UUID, reason: str) -> StockTransfer:
    """Qabul qilinmagan hujjatni yuboruvchi filial bekor qiladi: qoldiq o'z partiyalariga qaytadi."""
    t = _locked_transfer(db, user, transfer_id)
    if user.branch_id != t.from_branch_id:
        raise HTTPException(403, "Faqat yuboruvchi filial bekor qila oladi")
    for line in db.scalars(select(StockTransferLine).where(StockTransferLine.transfer_id == t.id)):
        batch = db.scalar(select(StockBatch).where(StockBatch.id == line.source_batch_id).with_for_update())
        batch.qty_remaining += line.qty
        db.add(StockMovement(item_id=line.item_id, batch_id=batch.id, kind=StockMovementKind.transfer_in, qty=line.qty, unit_cost=batch.unit_cost,
                             reason=f"{t.number} bekor qilindi", ref_type="transfer", ref_id=t.id, branch_id=t.from_branch_id, created_by=user.id))
    t.status, t.cancelled_at, t.cancel_reason = TransferStatus.cancelled, datetime.now(UTC), reason[:300]
    return t


def transfer_out(db: Session, t: StockTransfer) -> dict:
    names = {b.id: b.name for b in db.scalars(select(Branch).where(Branch.id.in_([t.from_branch_id, t.to_branch_id])))}
    rows = db.execute(select(StockTransferLine, StockItem).join(StockItem, StockTransferLine.item_id == StockItem.id)
                      .where(StockTransferLine.transfer_id == t.id).order_by(StockItem.name, StockTransferLine.expires_on.asc().nulls_last(),
                                                                              StockTransferLine.batch_no)).all()
    lines = [{"item_id": str(i.id), "item": i.name, "unit": i.unit, "batch_no": ln.batch_no, "expires_on": ln.expires_on, "qty": ln.qty,
              "unit_cost": ln.unit_cost, "amount": q2(ln.qty * ln.unit_cost)} for ln, i in rows]
    iso = lambda d: d.isoformat() if d else None          # noqa: E731
    return {"id": str(t.id), "number": t.number, "status": t.status, "from_branch_id": str(t.from_branch_id), "from_branch": names[t.from_branch_id],
            "to_branch_id": str(t.to_branch_id), "to_branch": names[t.to_branch_id], "notes": t.notes, "sent_at": iso(t.sent_at),
            "received_at": iso(t.received_at), "cancelled_at": iso(t.cancelled_at), "cancel_reason": t.cancel_reason,
            "total": sum((ln["amount"] for ln in lines), q2(0)), "lines": lines}
