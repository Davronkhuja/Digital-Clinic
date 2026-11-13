"""To'lovda avtomatik sarf (v1.9.5): to'liq to'langanda norma x miqdor FEFO bo'yicha, bir marta, yetmasa to'lov to'xtamaydi."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Invoice, StockBatch, StockMovement
from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")


def _item(client, h, name):
    return client.post("/warehouse/items", json={"name": name, "unit": "dona"}, headers=h).json()["id"]


def _receive(client, h, item, qty, batch, days, cost=100):
    body = {"lines": [{"item_id": item, "batch_no": batch, "qty": qty, "unit_cost": cost, "expires_on": (date.today() + timedelta(days=days)).isoformat()}]}
    assert client.post("/warehouse/receipts", json=body, headers=h).status_code == 201


def _service(client, h, name, norms):
    sid = client.post("/services", headers=h, json={"name": name, "price": 112000, "mxik": "09302001001000000", "package_code": "1500364",
                                                    "vat_percent": 12}).json()["id"]
    if norms:
        assert client.put(f"/warehouse/services/{sid}/materials", headers=h, json={"materials": [{"item_id": i, "qty": q} for i, q in norms]}).status_code == 200
    return sid


def _invoice(client, auth, lines):
    pid = client.post("/patients", json={**NEW, "name": "Sarf Bemor"}, headers=auth("admin")).json()["id"]
    return client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "issue": True,
                                                                   "lines": [{"service_id": s, "quantity": q} for s, q in lines]}).json()


def _pay(client, auth, inv, amount=None):
    body = {"method": "Cash", **({"amount": amount} if amount else {})}
    res = client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _consumption(inv_id):
    with SessionLocal() as db:
        return [(m.batch_id, m.qty) for m in db.scalars(select(StockMovement).where(StockMovement.kind == "Consumption", StockMovement.ref_id == inv_id))]


def test_full_payment_consumes_norm_times_quantity_fefo_once(client, auth):
    admin = auth("admin")
    syringe, gel = _item(client, admin, "Shprits"), _item(client, admin, "Gel")
    _receive(client, admin, syringe, 3, "S-LATE", 300)
    _receive(client, admin, syringe, 5, "S-SOON", 20)
    _receive(client, admin, gel, 10, "G-1", 100)
    svc = _service(client, admin, "Inyeksiya", [(syringe, 2), (gel, 0.5)])
    plain = _service(client, admin, "Normasiz xizmat", [])
    inv = _invoice(client, auth, [(svc, 3), (plain, 1)])                      # 3 marta inyeksiya: 6 shprits, 1.5 gel
    _pay(client, auth, inv, 50000)                                            # qisman: hali sarf yo'q
    assert _consumption(inv["id"]) == []
    paid = _pay(client, auth, inv)                                            # qoldig'i bilan to'liq
    assert paid["status"] == "Paid"
    with SessionLocal() as db:
        remaining = {b.batch_no: b.qty_remaining for b in db.scalars(select(StockBatch))}
        assert remaining == {"S-SOON": 0, "S-LATE": 2, "G-1": 8.5}            # 6 ta: avval S-SOON (5), keyin S-LATE (1) -> FEFO
        assert db.get(Invoice, inv["id"]).stock_consumed_at is not None
        moves = db.scalars(select(StockMovement).where(StockMovement.kind == "Consumption")).all()
        assert all(str(m.ref_id) == inv["id"] and "INV-" in m.reason for m in moves) and len(moves) == 3
    refund = client.post(f"/payments/{paid['id']}/refunds", headers=admin, json={"amount": 1000, "reason": "kichik qaytarish"})
    assert refund.status_code in (200, 201), refund.text
    _pay(client, auth, inv, 1000)                                             # qayta to'liq bo'ldi: qayta yozilmaydi
    assert len(_consumption(inv["id"])) == 3
    assert client.get("/warehouse/shortages", headers=admin).json() == []


def test_insufficient_stock_never_blocks_payment_and_shortage_is_resolved_later(client, auth):
    admin = auth("admin")
    item = _item(client, admin, "Kam material")
    _receive(client, admin, item, 4, "K-1", 60)
    svc = _service(client, admin, "Katta sarf", [(item, 3)])
    inv = _invoice(client, auth, [(svc, 2)])                                  # 6 kerak, 4 bor
    paid = _pay(client, auth, inv)
    assert paid["status"] == "Paid" and paid["receipt_status"] == "Issued"    # to'lov va chek to'xtamadi
    short = client.get("/warehouse/shortages", headers=admin).json()
    assert len(short) == 1 and short[0]["item"] == "Kam material" and short[0]["qty_missing"] == 2 and short[0]["invoice_number"] == inv["number"]
    assert client.get("/warehouse/alerts", headers=admin).json()["shortages"][0]["qty_missing"] == 2
    assert client.post(f"/warehouse/shortages/{short[0]['id']}/resolve", headers=admin).status_code == 409      # hali kirim yo'q
    _receive(client, admin, item, 10, "K-2", 90)
    assert client.post(f"/warehouse/shortages/{short[0]['id']}/resolve", headers=auth("doctor")).status_code == 403
    assert client.post(f"/warehouse/shortages/{short[0]['id']}/resolve", headers=admin).json() == []
    assert client.post(f"/warehouse/shortages/{short[0]['id']}/resolve", headers=admin).status_code == 409      # qayta hal qilinmaydi
    with SessionLocal() as db:
        assert {b.batch_no: b.qty_remaining for b in db.scalars(select(StockBatch))} == {"K-1": 0, "K-2": 8}
    assert client.post("/warehouse/shortages/00000000-0000-0000-0000-000000000000/resolve", headers=admin).status_code == 404


def test_expired_batch_is_not_consumed_and_unpaid_invoice_consumes_nothing(client, auth):
    admin = auth("admin")
    item = _item(client, admin, "Muddatli")
    _receive(client, admin, item, 5, "OLD", 30)
    svc = _service(client, admin, "Xizmat", [(item, 1)])
    with SessionLocal() as db:
        db.scalar(select(StockBatch)).expires_on = date.today() - timedelta(days=1)
        db.commit()
    unpaid = _invoice(client, auth, [(svc, 1)])
    assert _consumption(unpaid["id"]) == []
    _pay(client, auth, unpaid)
    assert _consumption(unpaid["id"]) == [] and len(client.get("/warehouse/shortages", headers=admin).json()) == 1   # yaroqli yo'q: yetishmovchilik
    with SessionLocal() as db:
        assert db.scalar(select(StockBatch.qty_remaining)) == 5                                                       # muddati o'tgan tegilmadi
