"""Kirim, partiyalar, qoldiq va minimal qoldiq ogohlantirishi (v1.9.1)."""
from datetime import date, timedelta

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import StockBatch, StockMovement


def _item(client, h, name="Shprits 5 ml", **kw):
    return client.post("/warehouse/items", json={"name": name, "kind": "Supply", "unit": "dona", **kw}, headers=h).json()["id"]


def _line(item, qty=100, cost=450, batch="B-1", days=365, **kw):
    return {"item_id": item, "batch_no": batch, "qty": qty, "unit_cost": cost,
            "expires_on": (date.today() + timedelta(days=days)).isoformat() if days is not None else None, **kw}


def test_receipt_creates_batches_movements_and_totals(client, auth):
    h = auth("admin")
    a, b = _item(client, h), _item(client, h, "Paxta 100 g", min_qty=5)
    res = client.post("/warehouse/receipts", headers=h, json={"supplier": "MedPlus", "doc_no": "N-17", "lines": [
        _line(a, 100, 450.50, "S-1"), _line(a, 50, 500, "S-2", days=90), _line(b, 10.5, 12000, "P-1", days=None)]})
    assert res.status_code == 201, res.text
    r = res.json()
    assert r["supplier"] == "MedPlus" and r["received_on"] == date.today().isoformat() and len(r["lines"]) == 3
    by_batch = {ln["batch_no"]: ln for ln in r["lines"]}
    assert by_batch["S-1"]["amount"] == 45050.0 and by_batch["P-1"]["amount"] == 126000.0
    assert r["total"] == 45050 + 25000 + 126000
    with SessionLocal() as db:                                                    # har qatorga partiya va harakat
        batches = db.scalars(select(StockBatch)).all()
        moves = db.scalars(select(StockMovement)).all()
        assert len(batches) == 3 and len(moves) == 3
        assert {str(m.batch_id) for m in moves} == {str(x.id) for x in batches}
        assert all(m.kind.value == "Receipt" and m.ref_id is not None for m in moves)
        assert sum(m.qty for m in moves) == sum(x.qty_remaining for x in batches) == 160.5
    got = client.get(f"/warehouse/receipts/{r['id']}", headers=h).json()
    assert got == r and client.get("/warehouse/receipts", headers=h).json()[0]["id"] == r["id"]
    assert client.get("/warehouse/receipts/00000000-0000-0000-0000-000000000000", headers=h).status_code == 404


def test_stock_balances_batches_ordering_and_low_alerts(client, auth):
    h = auth("admin")
    a, b = _item(client, h, "A material", min_qty=200), _item(client, h, "B material", min_qty=5)
    _item(client, h, "C material")
    client.post("/warehouse/receipts", headers=h, json={"lines": [_line(a, 100, 10, "A-late", days=300), _line(a, 40, 12, "A-soon", days=20),
                                                                  _line(b, 5, 100, "B-1", days=None)]})
    stock = {r["name"]: r for r in client.get("/warehouse/stock", headers=h).json()}
    assert stock["A material"]["qty"] == stock["A material"]["usable_qty"] == 140 and stock["A material"]["value"] == 100 * 10 + 40 * 12
    assert stock["A material"]["low"] is True and stock["B material"]["low"] is False             # 5 < 5 emas
    assert stock["C material"]["qty"] == 0 and stock["C material"]["low"] is False                 # min_qty=0: ogohlantirish yo'q
    assert [r["name"] for r in client.get("/warehouse/stock", params={"low_only": True}, headers=h).json()] == ["A material"]
    assert [x["name"] for x in client.get("/warehouse/alerts", headers=h).json()["low_stock"]] == ["A material"]
    rows = client.get("/warehouse/batches", params={"item_id": a}, headers=h).json()
    assert [x["batch_no"] for x in rows] == ["A-soon", "A-late"]                                   # muddat bo'yicha (FEFO tartibi)
    assert rows[0]["days_left"] == 20 and rows[0]["expired"] is False
    nodate = client.get("/warehouse/batches", params={"item_id": b}, headers=h).json()[0]
    assert nodate["expires_on"] is None and nodate["days_left"] is None


def test_expired_batch_is_not_usable(client, auth):
    h = auth("admin")
    a = _item(client, h, "Muddat material", min_qty=10)
    client.post("/warehouse/receipts", headers=h, json={"lines": [_line(a, 50, 10, "OK", days=100)]})
    with SessionLocal() as db:                                                                     # partiya muddati keyin o'tib ketdi
        b = db.scalar(select(StockBatch))
        b.expires_on = date.today() - timedelta(days=1)
        db.commit()
    row = client.get("/warehouse/stock", headers=h).json()[0]
    assert row["qty"] == 50 and row["usable_qty"] == 0 and row["expired_qty"] == 50 and row["low"] is True
    assert client.get("/warehouse/batches", headers=h).json()[0]["expired"] is True


def test_receipt_validation_and_permissions(client, auth):
    h = auth("admin")
    a = _item(client, h)
    ok = _line(a)
    post = lambda body, hh=h: client.post("/warehouse/receipts", json=body, headers=hh)           # noqa: E731
    assert post({"lines": []}).status_code == 422
    assert post({"lines": [_line(a, 0)]}).status_code == 422                                       # miqdor > 0
    assert post({"lines": [_line(a, -1)]}).status_code == 422
    assert post({"lines": [_line(a, 1.2345)]}).status_code == 422                                  # 3 xonadan ortiq
    assert post({"lines": [_line(a, 1, -5)]}).status_code == 422                                   # narx >= 0
    assert post({"lines": [_line(a, batch=" ")]}).status_code == 422
    assert post({"lines": [_line(a, days=-1)]}).status_code == 422                                 # muddati o'tgan
    assert post({"received_on": (date.today() + timedelta(days=1)).isoformat(), "lines": [ok]}).status_code == 422
    assert post({"lines": [{**ok, "item_id": "00000000-0000-0000-0000-000000000000"}]}).status_code == 422
    inactive = _item(client, h, "Faolsiz")
    client.put(f"/warehouse/items/{inactive}", json={"is_active": False}, headers=h)
    assert post({"lines": [_line(inactive)]}).status_code == 422
    with SessionLocal() as db:                                                                     # xato bo'lsa hech narsa yozilmaydi
        assert db.scalar(select(StockBatch)) is None
    assert post({"lines": [ok]}, auth("doctor")).status_code == 403
    assert post({"lines": [ok]}, auth("cashier")).status_code == 403
    assert post({"lines": [ok]}, auth("nurse")).status_code == 201
    assert client.get("/warehouse/stock", headers=auth("doctor")).status_code == 200
    assert client.delete("/warehouse/receipts/x", headers=h).status_code in (404, 405)
