"""Inventarizatsiya (v1.9.19): sanoq hujjati, farq bo'yicha avtomatik kirim/chiqim, ruxsat bilan tasdiq."""
from datetime import date, timedelta

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import StockBatch, StockMovement

ZERO = "00000000-0000-0000-0000-000000000000"


def _item(client, h, name):
    return client.post("/warehouse/items", json={"name": name, "unit": "dona"}, headers=h).json()["id"]


def _receive(client, h, item, qty, batch, days, cost=100):
    body = {"lines": [{"item_id": item, "batch_no": batch, "qty": qty, "unit_cost": cost, "expires_on": (date.today() + timedelta(days=days)).isoformat()}]}
    assert client.post("/warehouse/receipts", json=body, headers=h).status_code == 201


def _lines(count):
    return {ln["batch_no"]: ln for ln in count["lines"]}


def _stock(client, h):
    return {b["batch_no"]: b["qty_remaining"] for b in client.get("/warehouse/batches", headers=h).json()}


def _setup(client, auth):
    admin = auth("admin")
    a, b = _item(client, admin, "Material A"), _item(client, admin, "Material B")
    _receive(client, admin, a, 10, "A-1", 60, 100)
    _receive(client, admin, a, 20, "A-2", 200, 120)
    _receive(client, admin, b, 5, "B-1", 90, 1000)
    return admin, a, b


def test_count_flow_adjusts_with_movements_and_value(client, auth):
    admin, a, b = _setup(client, auth)
    nurse = auth("nurse")
    count = client.post("/warehouse/counts", json={"notes": "oy oxiri"}, headers=nurse).json()
    assert count["status"] == "Draft" and count["number"].startswith("SK-") and len(count["lines"]) == 3
    assert {k: v["expected_qty"] for k, v in _lines(count).items()} == {"A-1": 10, "A-2": 20, "B-1": 5}
    assert client.post("/warehouse/counts", json={}, headers=nurse).status_code == 409                       # bitta ochiq hujjat
    assert client.post(f"/warehouse/counts/{count['id']}/submit", headers=nurse).status_code == 422          # sanalmagan qatorlar bor
    ln = _lines(count)
    put = client.put(f"/warehouse/counts/{count['id']}/lines", headers=nurse, json={
        "counted": [{"line_id": ln["A-1"]["id"], "counted_qty": 8}, {"line_id": ln["A-2"]["id"], "counted_qty": 20}, {"line_id": ln["B-1"]["id"], "counted_qty": 6}],
        "extras": [{"item_id": b, "batch_no": "B-NEW", "expires_on": (date.today() + timedelta(days=120)).isoformat(), "unit_cost": 900, "counted_qty": 3}]})
    assert put.status_code == 200, put.text
    out = put.json()
    assert {k: v["diff"] for k, v in _lines(out).items()} == {"A-1": -2, "A-2": 0, "B-1": 1, "B-NEW": 3}
    assert out["shortage_value"] == 200 and out["surplus_value"] == 1000 + 2700 and out["net_value"] == 3500 and out["diff_lines"] == 3
    assert _lines(out)["B-NEW"]["found"] is True and _stock(client, admin) == {"A-1": 10, "A-2": 20, "B-1": 5}      # tasdiqgacha qoldiq o'zgarmaydi
    sub = client.post(f"/warehouse/counts/{count['id']}/submit", headers=nurse)
    assert sub.status_code == 200 and sub.json()["status"] == "Submitted" and sub.json()["submitted_at"]
    assert client.put(f"/warehouse/counts/{count['id']}/lines", headers=nurse, json={"counted": []}).status_code == 409   # yuborilgach o'zgarmaydi
    notes = client.get("/notifications", headers=admin).json()
    assert any(n["kind"] == "stock_count" and count["number"] in n["title"] for n in notes)                           # tasdiqlovchiga xabar
    assert client.post(f"/warehouse/counts/{count['id']}/approve", headers=nurse).status_code == 403                  # warehouse:approve yo'q
    done = client.post(f"/warehouse/counts/{count['id']}/approve", headers=admin)
    assert done.status_code == 200 and done.json()["status"] == "Approved"
    batches = client.get("/warehouse/batches", headers=admin).json()
    by = {}
    for x in batches:
        by.setdefault(x["batch_no"], 0)
        by[x["batch_no"]] += x["qty_remaining"]
    assert by == {"A-1": 8, "A-2": 20, "B-1": 6, "B-NEW": 3}                                                          # ko'p chiqqan: yangi partiya, kam chiqqan: kamaydi
    adj = client.get("/warehouse/movements", params={"kind": "Adjust"}, headers=admin).json()
    assert sorted((m["batch_no"], m["qty"]) for m in adj) == [("A-1", -2), ("B-1", 1), ("B-NEW", 3)] and all("Inventarizatsiya" in m["reason"] for m in adj)
    with SessionLocal() as db:                                                                                          # jurnal yaxlitligi
        for b in db.scalars(select(StockBatch)):
            assert db.scalar(select(func.coalesce(func.sum(StockMovement.qty), 0)).where(StockMovement.batch_id == b.id)) == b.qty_remaining
    assert client.post(f"/warehouse/counts/{count['id']}/approve", headers=admin).status_code == 409                   # ikki marta emas
    assert client.get("/warehouse/counts", headers=nurse).json()[0]["status"] == "Approved"
    assert client.post("/warehouse/counts", json={}, headers=nurse).status_code == 201                                  # yakunlangach yangisini ochish mumkin


def test_cancel_scope_validation_and_stale_count(client, auth):
    admin, a, b = _setup(client, auth)
    c1 = client.post("/warehouse/counts", json={"item_ids": [b]}, headers=admin).json()
    assert [ln["item"] for ln in c1["lines"]] == ["Material B"]                                                        # faqat tanlangan material
    assert client.post(f"/warehouse/counts/{c1['id']}/cancel", json={"reason": "x"}, headers=admin).status_code == 422
    out = client.post(f"/warehouse/counts/{c1['id']}/cancel", json={"reason": "noto'g'ri tanlov"}, headers=admin)
    assert out.status_code == 200 and out.json()["status"] == "Cancelled" and _stock(client, admin)["B-1"] == 5
    assert client.post(f"/warehouse/counts/{c1['id']}/cancel", json={"reason": "yana"}, headers=admin).status_code == 409
    assert client.post("/warehouse/counts", json={"item_ids": [ZERO]}, headers=admin).status_code == 422               # sanaladigan qoldiq yo'q
    # sanoqdan keyin qoldiq o'zgargan: kamayish yozilmaydi
    c2 = client.post("/warehouse/counts", json={"item_ids": [a]}, headers=admin).json()
    ln = _lines(c2)
    client.put(f"/warehouse/counts/{c2['id']}/lines", headers=admin, json={"counted": [{"line_id": ln["A-1"]["id"], "counted_qty": 2}, {"line_id": ln["A-2"]["id"], "counted_qty": 20}]})
    client.post(f"/warehouse/counts/{c2['id']}/submit", headers=admin)
    client.post("/warehouse/issues", json={"item_id": a, "qty": 5, "reason": "sanoq paytida chiqim"}, headers=admin)      # FEFO: A-1 dan 5 ta (10 -> 5); sanoq 2 (farq -8)
    stale = client.post(f"/warehouse/counts/{c2['id']}/approve", headers=admin)
    assert stale.status_code == 409 and "o'zgargan" in stale.json()["detail"]
    assert _stock(client, admin)["A-1"] == 5                                                                            # hech narsa yozilmadi
    assert client.get(f"/warehouse/counts/{ZERO}", headers=admin).status_code == 404
    other = client.post("/branches", json={"name": "Sanoq filiali"}, headers=admin).json()["id"]
    assert client.get(f"/warehouse/counts/{c2['id']}", headers={**admin, "X-Branch-Id": other}).status_code == 404       # boshqa filial ko'rmaydi
    assert client.put(f"/warehouse/counts/{c2['id']}/lines", headers=auth("doctor"), json={"counted": []}).status_code == 403
