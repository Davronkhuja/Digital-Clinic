"""Yaroqlilik muddati ogohlantirishi (30 kun) va hisobdan chiqarish (v1.9.3)."""
from datetime import date, timedelta

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import StockBatch


def _setup(client, h):
    item = client.post("/warehouse/items", json={"name": "Vaktsina", "unit": "doza", "min_qty": 5}, headers=h).json()["id"]
    lines = [("TODAY", 3, 0), ("D10", 4, 10), ("D30", 5, 30), ("D31", 6, 31), ("D200", 7, 200), ("NODATE", 8, None), ("OLD", 9, 5)]
    body = [{"item_id": item, "batch_no": b, "qty": q, "unit_cost": 100,
             "expires_on": (date.today() + timedelta(days=d)).isoformat() if d is not None else None} for b, q, d in lines]
    assert client.post("/warehouse/receipts", json={"lines": body}, headers=h).status_code == 201
    with SessionLocal() as db:                                                       # OLD: muddati keyin o'tib ketdi
        db.scalar(select(StockBatch).where(StockBatch.batch_no == "OLD")).expires_on = date.today() - timedelta(days=2)
        db.commit()
    return item


def test_alerts_expiring_within_30_days_and_expired(client, auth):
    h = auth("admin")
    _setup(client, h)
    out = client.get("/warehouse/alerts", headers=h).json()
    assert out["expiry_days"] == 30
    assert [b["batch_no"] for b in out["expiring"]] == ["TODAY", "D10", "D30"]       # 30 kun chegarasi kiradi, 31 kirmaydi; muddatsiz ham
    assert [b["days_left"] for b in out["expiring"]] == [0, 10, 30]
    assert [b["batch_no"] for b in out["expired"]] == ["OLD"] and out["expired"][0]["days_left"] == -2
    assert client.get("/warehouse/alerts", params={"days": 60}, headers=h).json()["expiring"][-1]["batch_no"] == "D31"
    assert client.get("/warehouse/alerts", params={"days": 0}, headers=h).status_code == 422
    assert out["low_stock"] == []                                                    # yaroqli qoldiq 33 >= 5
    assert client.get("/warehouse/alerts", headers=auth("cashier")).status_code == 403


def test_empty_batches_do_not_alert(client, auth):
    h = auth("admin")
    item = _setup(client, h)
    client.post("/warehouse/issues", json={"item_id": item, "qty": 3, "reason": "bugun"}, headers=h)   # TODAY (3) tugaydi
    assert "TODAY" not in [b["batch_no"] for b in client.get("/warehouse/alerts", headers=h).json()["expiring"]]


def test_writeoff_batch_partial_and_full_with_reason_and_ledger(client, auth):
    h = auth("admin")
    _setup(client, h)
    old = next(b for b in client.get("/warehouse/batches", headers=h).json() if b["batch_no"] == "OLD")
    res = client.post("/warehouse/writeoffs", json={"batch_id": old["id"], "qty": 4, "reason": "muddati o'tgan"}, headers=h)
    assert res.status_code == 201 and res.json()[0]["kind"] == "Writeoff" and res.json()[0]["qty"] == -4
    assert client.get("/warehouse/alerts", headers=h).json()["expired"][0]["qty_remaining"] == 5
    assert client.post("/warehouse/writeoffs", json={"batch_id": old["id"], "qty": 6, "reason": "ortiqcha"}, headers=h).status_code == 409
    assert client.post("/warehouse/writeoffs", json={"batch_id": old["id"], "reason": "qolgani"}, headers=h).status_code == 201   # butunlay
    assert client.get("/warehouse/alerts", headers=h).json()["expired"] == []
    assert client.post("/warehouse/writeoffs", json={"batch_id": old["id"], "reason": "yana"}, headers=h).status_code == 409        # qoldiq yo'q
    assert client.post("/warehouse/writeoffs", json={"batch_id": old["id"], "reason": "x"}, headers=h).status_code == 422
    assert client.post("/warehouse/writeoffs", json={"batch_id": "00000000-0000-0000-0000-000000000000", "reason": "yo'q"}, headers=h).status_code == 404
    assert client.post("/warehouse/writeoffs", json={"batch_id": old["id"], "reason": "ruxsat"}, headers=auth("doctor")).status_code == 403
    moves = client.get("/warehouse/movements", params={"kind": "Writeoff"}, headers=h).json()
    assert sorted(m["qty"] for m in moves) == [-5, -4] and all(m["reason"] for m in moves)
    stock = client.get("/warehouse/stock", headers=h).json()[0]
    assert stock["expired_qty"] == 0 and stock["qty"] == 33
