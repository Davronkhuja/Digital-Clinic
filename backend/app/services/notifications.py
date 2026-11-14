# ruff: noqa: E501
"""Ichki bildirishnomalar: filial va ruxsat bo'yicha. Takrorlanmaslik `dedupe_key` bilan."""
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Branch, Notification, StockItem
from app.services.periods import clinic_today

WAREHOUSE = "warehouse:write"      # ombor mas'uli: kirim/chiqim qila oladigan xodimlar


def notify(db: Session, *, branch_id: uuid.UUID, permission: str, kind: str, title: str, body: str | None = None, link: str | None = None,
           dedupe_key: str | None = None) -> Notification | None:
    """Bildirishnoma yaratadi; `dedupe_key` bo'yicha allaqachon bor bo'lsa yaratmaydi (None qaytaradi)."""
    if dedupe_key and db.scalar(select(Notification.id).where(Notification.dedupe_key == dedupe_key)):
        return None
    n = Notification(branch_id=branch_id, permission=permission, kind=kind, title=title[:200], body=body, link=link, dedupe_key=dedupe_key)
    db.add(n)
    db.flush()
    return n


def check_low_stock(db: Session, branch_id: uuid.UUID, item_ids: list[uuid.UUID] | None = None) -> int:
    """Yaroqli qoldig'i minimaldan kam materiallar uchun (kuniga bir marta har material) bildirishnoma."""
    from app.services import warehouse as wh

    today = clinic_today().isoformat()
    made = 0
    for row in wh.stock_rows(db, branch_id, low_only=True):
        if item_ids is not None and uuid.UUID(row["item_id"]) not in item_ids:
            continue
        n = notify(db, branch_id=branch_id, permission=WAREHOUSE, kind="stock_low", link="/warehouse",
                   title=f"Minimal qoldiqdan kam: {row['name']}",
                   body=f"Yaroqli qoldiq {row['usable_qty']:g} {row['unit']}, minimal {row['min_qty']:g} {row['unit']}",
                   dedupe_key=f"low:{branch_id}:{row['item_id']}:{today}")
        made += 1 if n else 0
    return made


def notify_shortage(db: Session, *, branch_id: uuid.UUID, shortage_id: uuid.UUID, item: StockItem, qty, invoice_number: str) -> None:
    notify(db, branch_id=branch_id, permission=WAREHOUSE, kind="stock_shortage", link="/warehouse",
           title=f"Omborda yetmadi: {item.name}", body=f"{invoice_number}: {qty:g} {item.unit} yetmadi. Kirimdan keyin 'Yetishmovchilik' bo'limida yozing.",
           dedupe_key=f"shortage:{shortage_id}")


def scan_branch(db: Session, branch_id: uuid.UUID, days: int = 30) -> dict[str, int]:
    """Kunlik tekshiruv (Celery): minimal qoldiq, `days` ichida muddati tugaydigan va muddati o'tgan partiyalar. Takrorlanmaydi (kuniga bir marta)."""
    from app.services import warehouse as wh

    today = clinic_today()
    made = {"low": check_low_stock(db, branch_id), "expiring": 0, "expired": 0}
    for b in wh.batch_rows(db, branch_id, expiring_within=days):
        key = "expired" if b["expired"] else "expiring"
        if b["expired"]:
            title, body = f"Muddati o'tgan: {b['item']}", f"Partiya {b['batch_no']}: {b['qty_remaining']:g} {b['unit']} qoldi. Hisobdan chiqaring."
        else:
            title, body = f"Muddati {b['days_left']} kunda tugaydi: {b['item']}", f"Partiya {b['batch_no']}, {b['expires_on']}: {b['qty_remaining']:g} {b['unit']}."
        # muddati yaqin: haftada bir eslatiladi; muddati o'tgan: kuniga bir
        period = today.isoformat() if b["expired"] else f"{today.isocalendar().year}-W{today.isocalendar().week}"
        if notify(db, branch_id=branch_id, permission=WAREHOUSE, kind=f"stock_{key}", title=title, body=body, link="/warehouse",
                  dedupe_key=f"{key}:{b['id']}:{period}"):
            made[key] += 1
    return made


def scan_all(db: Session) -> dict[str, int]:
    total = {"low": 0, "expiring": 0, "expired": 0}
    for bid in db.scalars(select(Branch.id).where(Branch.is_active.is_(True))):
        for k, v in scan_branch(db, bid).items():
            total[k] += v
    db.commit()
    return total


def prune(db: Session, keep_days: int = 90) -> None:
    """Eski bildirishnomalar tozalanadi (o'qilgan yozuvlar bilan: CASCADE)."""
    from datetime import UTC, datetime

    from sqlalchemy import delete
    db.execute(delete(Notification).where(Notification.created_at < datetime.now(UTC) - timedelta(days=keep_days)))
