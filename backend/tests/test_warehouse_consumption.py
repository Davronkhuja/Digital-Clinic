"""Xizmat bajarilganda avtomatik sarf (v1.9.15): to'lov sarf yozmaydi; bajarildi = qator belgisi yoki qabul Completed; FEFO, bir marta,
bajarilmagan deb qaytarilsa material qaytadi, yetmasa qoldiq manfiyga tushmaydi."""
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import StockBatch, StockMovement
from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")
DOC = "Dr. Behruz Rustamov"


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


def _patient(client, auth):
    return client.post("/patients", json={**NEW, "name": "Sarf Bemor"}, headers=auth("admin")).json()["id"]


def _invoice(client, auth, lines, pid=None, appointment_id=None):
    body = {"patient_id": pid or _patient(client, auth), "issue": True, "lines": [{"service_id": s, "quantity": q} for s, q in lines]}
    if appointment_id:
        body["appointment_id"] = appointment_id
    res = client.post("/invoices", headers=auth("cashier"), json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _pay(client, auth, inv, amount=None):
    res = client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json={"method": "Cash", **({"amount": amount} if amount else {})})
    assert res.status_code == 201, res.text
    return res.json()


def _perform(client, h, inv, line):
    return client.post(f"/invoices/{inv['id']}/lines/{line['id']}/perform", headers=h)


def _remaining():
    with SessionLocal() as db:
        return {b.batch_no: b.qty_remaining for b in db.scalars(select(StockBatch))}


def _moves(kind):
    with SessionLocal() as db:
        return [(m.item_id, m.qty) for m in db.scalars(select(StockMovement).where(StockMovement.kind == kind))]


def _appointment(client, auth, pid, time="10:00"):
    res = client.post("/appointments", headers=auth("admin"), json={"patient_id": pid, "doctor": DOC, "date": (date.today() + timedelta(days=3)).isoformat(),
                                                                    "time": time, "type": "Konsultatsiya", "override_reason": "sarf testi"})
    assert res.status_code == 201, res.text
    return res.json()


def test_payment_never_consumes_perform_does_fefo_once(client, auth):
    admin = auth("admin")
    syringe, gel = _item(client, admin, "Shprits"), _item(client, admin, "Gel")
    _receive(client, admin, syringe, 3, "S-LATE", 300)
    _receive(client, admin, syringe, 5, "S-SOON", 20)
    _receive(client, admin, gel, 10, "G-1", 100)
    svc = _service(client, admin, "Inyeksiya", [(syringe, 2), (gel, 0.5)])
    plain = _service(client, admin, "Normasiz xizmat", [])
    inv = _invoice(client, auth, [(svc, 3), (plain, 1)])                        # 3 marta inyeksiya: 6 shprits, 1.5 gel
    assert _pay(client, auth, inv)["status"] == "Paid"                          # to'lov sarf yozmaydi
    assert _remaining() == {"S-LATE": 3, "S-SOON": 5, "G-1": 10} and _moves("Consumption") == []
    line = inv["lines"][0]
    assert line["performed_at"] is None and client.get(f"/invoices/{inv['id']}", headers=admin).json()["lines"][0]["performed_at"] is None
    assert _perform(client, auth("cashier"), inv, line).status_code == 403      # bajarish: appointments:write
    done = _perform(client, auth("doctor"), inv, line)
    assert done.status_code == 200 and done.json()["lines"][0]["performed_at"] and done.json()["lines"][1]["performed_at"] is None
    assert _remaining() == {"S-SOON": 0, "S-LATE": 2, "G-1": 8.5}               # 6 ta: avval S-SOON (5), keyin S-LATE (1) -> FEFO
    assert _perform(client, auth("doctor"), inv, line).status_code == 409       # ikki marta yozilmaydi
    assert len(_moves("Consumption")) == 3
    assert _perform(client, auth("doctor"), inv, inv["lines"][1]).status_code == 200      # normasiz xizmat: belgi bor, sarf yo'q
    assert len(_moves("Consumption")) == 3 and client.get("/warehouse/shortages", headers=admin).json() == []


def test_completed_appointment_performs_linked_invoice_and_late_invoice(client, auth):
    admin = auth("admin")
    item = _item(client, admin, "Material")
    _receive(client, admin, item, 20, "M-1", 90)
    svc = _service(client, admin, "Konsultatsiya+", [(item, 2)])
    pid = _patient(client, auth)
    appt = _appointment(client, auth, pid)
    inv = _invoice(client, auth, [(svc, 1)], pid, appt["id"])
    _pay(client, auth, inv)
    assert _remaining() == {"M-1": 20}
    assert client.patch(f"/appointments/{appt['id']}/status", params={"status": "Completed"}, headers=auth("doctor")).status_code == 200
    assert _remaining() == {"M-1": 18}                                          # qabul yakunlandi: xizmat bajarildi
    client.patch(f"/appointments/{appt['id']}/status", params={"status": "Completed"}, headers=auth("doctor"))
    assert _remaining() == {"M-1": 18}                                          # qayta yakunlash ikkinchi marta yozmaydi
    # qabul avval yakunlangan, hisob-faktura keyin chiqariladi: chiqarilganda bajarilgan hisoblanadi
    pid2 = _patient(client, auth)
    appt2 = _appointment(client, auth, pid2, "11:00")
    client.patch(f"/appointments/{appt2['id']}/status", params={"status": "Completed"}, headers=auth("doctor"))
    _invoice(client, auth, [(svc, 1)], pid2, appt2["id"])
    assert _remaining() == {"M-1": 16}
    pid3 = _patient(client, auth)                                               # bekor qilingan qabul bajarilmaydi
    appt3 = _appointment(client, auth, pid3, "12:00")
    _invoice(client, auth, [(svc, 1)], pid3, appt3["id"])
    client.patch(f"/appointments/{appt3['id']}/status", params={"status": "Cancelled"}, headers=auth("doctor"))
    assert _remaining() == {"M-1": 16}


def test_unperform_returns_material_but_refund_of_performed_does_not(client, auth):
    admin = auth("admin")
    item = _item(client, admin, "Qaytadigan")
    _receive(client, admin, item, 5, "R-SOON", 20)
    _receive(client, admin, item, 10, "R-LATE", 200)
    svc = _service(client, admin, "Qaytarish xizmati", [(item, 3)])
    inv = _invoice(client, auth, [(svc, 2)])                                    # 6 ta: R-SOON 5, R-LATE 1
    paid = _pay(client, auth, inv)
    _perform(client, auth("doctor"), inv, inv["lines"][0])
    assert _remaining() == {"R-SOON": 0, "R-LATE": 9}
    assert client.delete(f"/invoices/{inv['id']}/lines/{inv['lines'][0]['id']}/perform", headers=auth("cashier")).status_code == 403
    undone = client.delete(f"/invoices/{inv['id']}/lines/{inv['lines'][0]['id']}/perform", headers=auth("doctor"))
    assert undone.status_code == 200 and undone.json()["lines"][0]["performed_at"] is None
    assert _remaining() == {"R-SOON": 5, "R-LATE": 10}                          # o'z partiyalariga qaytdi
    assert sorted(q for _, q in _moves("Return")) == [1, 5]
    assert client.delete(f"/invoices/{inv['id']}/lines/{inv['lines'][0]['id']}/perform", headers=auth("doctor")).status_code == 409
    with SessionLocal() as db:                                                  # jurnal yaxlitligi
        for b in db.scalars(select(StockBatch)):
            assert db.scalar(select(func.coalesce(func.sum(StockMovement.qty), 0)).where(StockMovement.batch_id == b.id)) == b.qty_remaining
    # bajarilgan xizmat pulini qaytarish materialni qaytarmaydi
    _perform(client, auth("doctor"), inv, inv["lines"][0])
    assert _remaining() == {"R-SOON": 0, "R-LATE": 9}
    assert client.post(f"/payments/{paid['id']}/refunds", headers=admin, json={"amount": 112000 * 2, "reason": "to'liq qaytarish"}).status_code == 201
    assert _remaining() == {"R-SOON": 0, "R-LATE": 9}
    # to'liq qaytarilgan hisob-fakturada yangi xizmat bajarilmaydi (bajarilmagan qator: nomi bilan alohida hisob-faktura)
    inv2 = _invoice(client, auth, [(svc, 1)])
    paid2 = _pay(client, auth, inv2)
    client.post(f"/payments/{paid2['id']}/refunds", headers=admin, json={"amount": 112000, "reason": "bajarilmadi"})
    r = _perform(client, auth("doctor"), inv2, inv2["lines"][0])
    assert r.status_code == 409 and _remaining() == {"R-SOON": 0, "R-LATE": 9}        # bajarilmagan qaytarilsa: sarf yo'q, material tegilmaydi


def test_perform_rules_draft_cancelled_and_unknown(client, auth):
    admin = auth("admin")
    svc = _service(client, admin, "Qoralama xizmat", [])
    pid = _patient(client, auth)
    draft = client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "lines": [{"service_id": svc, "quantity": 1}]}).json()
    assert _perform(client, auth("doctor"), draft, draft["lines"][0]).status_code == 409
    inv = _invoice(client, auth, [(svc, 1)])
    assert client.post(f"/invoices/{inv['id']}/lines/00000000-0000-0000-0000-000000000000/perform", headers=auth("doctor")).status_code == 404
    client.post(f"/invoices/{inv['id']}/cancel", headers=auth("cashier"), json={"reason": "xato yozildi"})
    assert _perform(client, auth("doctor"), inv, inv["lines"][0]).status_code == 409


def test_shortage_never_negative_resolved_later_and_closed_by_unperform(client, auth):
    admin = auth("admin")
    item = _item(client, admin, "Kam material")
    _receive(client, admin, item, 4, "K-1", 60)
    svc = _service(client, admin, "Katta sarf", [(item, 3)])
    inv = _invoice(client, auth, [(svc, 2)])                                    # 6 kerak, 4 bor
    assert _pay(client, auth, inv)["receipt_status"] == "Issued"
    assert _perform(client, auth("doctor"), inv, inv["lines"][0]).status_code == 200          # xizmat bajarildi, to'xtamadi
    assert _remaining() == {"K-1": 0}                                           # manfiyga tushmadi
    short = client.get("/warehouse/shortages", headers=admin).json()
    assert len(short) == 1 and short[0]["qty_missing"] == 2 and short[0]["invoice_number"] == inv["number"]
    assert client.get("/warehouse/alerts", headers=admin).json()["shortages"][0]["qty_missing"] == 2
    assert client.post(f"/warehouse/shortages/{short[0]['id']}/resolve", headers=admin).status_code == 409
    _receive(client, admin, item, 10, "K-2", 90)
    assert client.post(f"/warehouse/shortages/{short[0]['id']}/resolve", headers=auth("doctor")).status_code == 403
    assert client.post(f"/warehouse/shortages/{short[0]['id']}/resolve", headers=admin).json() == []
    assert _remaining() == {"K-1": 0, "K-2": 8}
    assert client.post(f"/warehouse/shortages/{short[0]['id']}/resolve", headers=admin).status_code == 409
    client.delete(f"/invoices/{inv['id']}/lines/{inv['lines'][0]['id']}/perform", headers=auth("doctor"))   # hammasi qaytadi (4 + 2)
    assert _remaining() == {"K-1": 4, "K-2": 10}
    # yetishmovchilik bilan bajarilgan, keyin bekor qilingan: yetishmovchilik yopiladi
    inv2 = _invoice(client, auth, [(svc, 5)])                                   # 15 kerak, 14 bor
    _perform(client, auth("doctor"), inv2, inv2["lines"][0])
    assert len(client.get("/warehouse/shortages", headers=admin).json()) == 1
    client.delete(f"/invoices/{inv2['id']}/lines/{inv2['lines'][0]['id']}/perform", headers=auth("doctor"))
    assert client.get("/warehouse/shortages", headers=admin).json() == [] and _remaining() == {"K-1": 4, "K-2": 10}


def test_expired_batch_is_not_consumed(client, auth):
    admin = auth("admin")
    item = _item(client, admin, "Muddatli")
    _receive(client, admin, item, 5, "OLD", 30)
    svc = _service(client, admin, "Xizmat", [(item, 1)])
    with SessionLocal() as db:
        db.scalar(select(StockBatch)).expires_on = date.today() - timedelta(days=1)
        db.commit()
    inv = _invoice(client, auth, [(svc, 1)])
    _pay(client, auth, inv)
    _perform(client, auth("doctor"), inv, inv["lines"][0])
    assert _remaining() == {"OLD": 5} and len(client.get("/warehouse/shortages", headers=admin).json()) == 1    # yaroqli yo'q: yetishmovchilik
