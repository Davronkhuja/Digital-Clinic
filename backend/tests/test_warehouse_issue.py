"""FEFO chiqim (v1.9.2): muddati bo'yicha, muddatsiz oxirida, muddati o'tgan ishlatilmaydi, yetmasa 409, jurnal qoldiqqa teng."""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import StockBatch, StockMovement


def _item(client, h, name="Shprits"):
    return client.post("/warehouse/items", json={"name": name, "unit": "dona"}, headers=h).json()["id"]


def _receive(client, h, item, *lines):
    """lines: (partiya, miqdor, narx, muddat kunlari yoki None)"""
    body = [{"item_id": item, "batch_no": b, "qty": q, "unit_cost": c,
             "expires_on": (date.today() + timedelta(days=d)).isoformat() if d is not None else None} for b, q, c, d in lines]
    res = client.post("/warehouse/receipts", json={"lines": body}, headers=h)
    assert res.status_code == 201, res.text


def _issue(client, h, item, qty, reason="3-kabinet"):
    return client.post("/warehouse/issues", json={"item_id": item, "qty": qty, "reason": reason}, headers=h)


def _remaining(batch_no):
    with SessionLocal() as db:
        return db.scalar(select(StockBatch.qty_remaining).where(StockBatch.batch_no == batch_no))


def test_fefo_takes_earliest_expiry_first_and_no_date_last(client, auth):
    h = auth("admin")
    item = _item(client, h)
    # kirish tartibi muddat tartibiga teskari: FEFO muddat bo'yicha olishi kerak
    _receive(client, h, item, ("NO-DATE", 100, 5, None), ("LATE", 30, 10, 300), ("SOON", 20, 12, 15), ("MID", 10, 11, 90))
    res = _issue(client, h, item, 45)
    assert res.status_code == 200, res.text
    out = res.json()
    assert [(a["batch_no"], a["qty"]) for a in out["allocations"]] == [("SOON", 20), ("MID", 10), ("LATE", 15)]
    assert out["qty"] == 45 and out["total_cost"] == 20 * 12 + 10 * 11 + 15 * 10
    assert (_remaining("SOON"), _remaining("MID"), _remaining("LATE"), _remaining("NO-DATE")) == (0, 0, 15, 100)
    out2 = _issue(client, h, item, 40).json()                                                 # LATE tugagach muddatsizga o'tadi
    assert [(a["batch_no"], a["qty"]) for a in out2["allocations"]] == [("LATE", 15), ("NO-DATE", 25)]
    stock = client.get("/warehouse/stock", headers=h).json()[0]
    assert stock["qty"] == 75 and stock["value"] == 75 * 5


def test_same_expiry_prefers_earlier_receipt_and_decimal_quantities(client, auth):
    h = auth("admin")
    item = _item(client, h, "Suyuqlik")
    _receive(client, h, item, ("FIRST", 2.5, 100, 60))
    _receive(client, h, item, ("SECOND", 2.5, 100, 60))
    out = _issue(client, h, item, 3.25).json()
    assert [(a["batch_no"], a["qty"]) for a in out["allocations"]] == [("FIRST", 2.5), ("SECOND", 0.75)]
    assert out["total_cost"] == 325 and _remaining("SECOND") == Decimal("1.75")


def test_expired_batch_is_skipped_and_insufficient_changes_nothing(client, auth):
    h = auth("admin")
    item = _item(client, h)
    _receive(client, h, item, ("OLD", 50, 10, 30), ("NEW", 10, 10, 200))
    with SessionLocal() as db:
        db.scalar(select(StockBatch).where(StockBatch.batch_no == "OLD")).expires_on = date.today() - timedelta(days=1)
        db.commit()
    res = _issue(client, h, item, 11)                                                          # yaroqli faqat 10
    assert res.status_code == 409 and "yaroqli 10" in res.json()["detail"] and "muddati o'tgan 50" in res.json()["detail"]
    assert (_remaining("OLD"), _remaining("NEW")) == (50, 10)                                  # hech narsa o'zgarmadi
    ok = _issue(client, h, item, 10).json()
    assert [a["batch_no"] for a in ok["allocations"]] == ["NEW"]                               # muddati o'tgan olinmadi
    assert _issue(client, h, item, 1).status_code == 409


def test_movement_journal_matches_batches_and_is_audited(client, auth):
    h = auth("nurse")
    item = _item(client, auth("admin"))
    _receive(client, auth("admin"), item, ("A", 100, 10, 30), ("B", 100, 10, 60))
    _issue(client, h, item, 130, "Protsedura xonasi")
    moves = client.get("/warehouse/movements", params={"item_id": item}, headers=h).json()
    assert [m["kind"] for m in moves].count("Issue") == 2 and [m["kind"] for m in moves].count("Receipt") == 2
    issue = [m for m in moves if m["kind"] == "Issue"]
    assert sorted(m["qty"] for m in issue) == [-100, -30] and all(m["reason"] == "Protsedura xonasi" and m["by"] for m in issue)
    assert [m["kind"] for m in client.get("/warehouse/movements", params={"kind": "Receipt"}, headers=h).json()] == ["Receipt", "Receipt"]
    with SessionLocal() as db:                                                                 # har partiya: harakatlar yig'indisi = qoldiq
        for b in db.scalars(select(StockBatch)):
            assert db.scalar(select(func.sum(StockMovement.qty)).where(StockMovement.batch_id == b.id)) == b.qty_remaining
        from app.models import AuditLog
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_type == "stock_issue")) == 1


def test_issue_validation_and_permissions(client, auth):
    admin = auth("admin")
    item = _item(client, admin)
    _receive(client, admin, item, ("A", 10, 10, 30))
    post = lambda body, h=admin: client.post("/warehouse/issues", json=body, headers=h)       # noqa: E731
    assert post({"item_id": item, "qty": 0, "reason": "xona"}).status_code == 422
    assert post({"item_id": item, "qty": -1, "reason": "xona"}).status_code == 422
    assert post({"item_id": item, "qty": 1, "reason": "x"}).status_code == 422                 # sabab majburiy
    assert post({"item_id": "00000000-0000-0000-0000-000000000000", "qty": 1, "reason": "xona"}).status_code == 422
    assert post({"item_id": item, "qty": 1, "reason": "xona"}, auth("doctor")).status_code == 403
    assert post({"item_id": item, "qty": 1, "reason": "xona"}, auth("nurse")).status_code == 200
    assert client.get("/warehouse/movements", headers=auth("cashier")).status_code == 403
