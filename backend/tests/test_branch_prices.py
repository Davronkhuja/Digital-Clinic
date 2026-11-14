"""Filial bo'yicha narx (v1.9.21): xizmat narxi filialda asosiydan farqli bo'lishi mumkin; hisob-faktura va tannarx shunga qarab."""
import pytest

from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")
SERVICE = {"name": "Filial narxli xizmat", "price": 100000, "mxik": "09302001001000000", "package_code": "1500364", "vat_percent": 12}


def _on(h, bid):
    return {**h, "X-Branch-Id": bid}


@pytest.fixture
def world(client, auth):
    admin = auth("admin")
    b = client.post("/branches", json={"name": "Qimmat filial"}, headers=admin).json()["id"]
    svc = client.post("/services", headers=admin, json=SERVICE).json()
    return admin, _on(admin, b), b, svc


def _invoice(client, h, svc_id, qty=1):
    pid = client.post("/patients", json={**NEW, "name": "Narx Bemor"}, headers=h).json()["id"]
    res = client.post("/invoices", headers=h, json={"patient_id": pid, "issue": True, "lines": [{"service_id": svc_id, "quantity": qty}]})
    assert res.status_code == 201, res.text
    return res.json()


def test_branch_price_only_changes_that_branch_and_invoices_use_it(client, auth, world):
    admin, other, b, svc = world
    assert svc["branch_price"] is None and svc["effective_price"] == 100000
    put = client.put(f"/services/{svc['id']}/branch-price", json={"price": 130000}, headers=other)
    assert put.status_code == 200 and put.json()["price"] == 100000 and put.json()["branch_price"] == 130000 and put.json()["effective_price"] == 130000
    main = next(s for s in client.get("/services", headers=admin).json() if s["id"] == svc["id"])
    there = next(s for s in client.get("/services", headers=other).json() if s["id"] == svc["id"])
    assert (main["effective_price"], main["branch_price"]) == (100000, None) and (there["effective_price"], there["branch_price"]) == (130000, 130000)
    assert client.get(f"/services/{svc['id']}/branch-prices", headers=admin).json() == [{"branch_id": b, "branch": "Qimmat filial", "price": 130000}]
    inv_main, inv_other = _invoice(client, admin, svc["id"], 2), _invoice(client, other, svc["id"], 2)
    assert (inv_main["total"], inv_main["lines"][0]["unit_price"]) == (200000, 100000)                                   # asosiy filial: asosiy narx
    assert (inv_other["total"], inv_other["lines"][0]["unit_price"]) == (260000, 130000)                                 # ikkinchi filial: filial narxi
    assert round(inv_other["vat_total"], 2) == round(260000 * 12 / 112, 2)                                               # QQS filial narxidan ajratiladi
    client.put(f"/services/{svc['id']}/branch-price", json={"price": 150000}, headers=other)                              # o'zgartirish: yangi hisob-fakturalarga
    assert _invoice(client, other, svc["id"])["total"] == 150000
    assert client.get(f"/invoices/{inv_other['id']}", headers=other).json()["total"] == 260000                           # yozilgani o'zgarmadi
    removed = client.delete(f"/services/{svc['id']}/branch-price", headers=other)
    assert removed.status_code == 200 and removed.json()["branch_price"] is None and removed.json()["effective_price"] == 100000
    assert _invoice(client, other, svc["id"])["total"] == 100000                                                          # asosiy narxga qaytdi
    assert client.delete(f"/services/{svc['id']}/branch-price", headers=other).status_code == 404


def test_draft_update_uses_invoice_branch_price_and_cost_margin_follow(client, auth, world):
    admin, other, b, svc = world
    client.put(f"/services/{svc['id']}/branch-price", json={"price": 224000}, headers=other)
    pid = client.post("/patients", json={**NEW, "name": "Qoralama Bemor"}, headers=other).json()["id"]
    draft = client.post("/invoices", headers=other, json={"patient_id": pid, "lines": [{"service_id": svc["id"], "quantity": 1}]}).json()
    assert draft["total"] == 224000
    upd = client.put(f"/invoices/{draft['id']}", headers=other, json={"lines": [{"service_id": svc["id"], "quantity": 2}]})
    assert upd.status_code == 200 and upd.json()["total"] == 448000
    item = client.post("/warehouse/items", json={"name": "Narx materiali", "unit": "dona"}, headers=admin).json()["id"]
    client.put(f"/warehouse/services/{svc['id']}/materials", headers=admin, json={"materials": [{"item_id": item, "qty": 1}]})
    from datetime import date, timedelta
    for h in (admin, other):
        client.post("/warehouse/receipts", headers=h, json={"lines": [{"item_id": item, "batch_no": "N-1", "qty": 5, "unit_cost": 1000,
                                                                      "expires_on": (date.today() + timedelta(days=90)).isoformat()}]})
    c_main = client.get(f"/warehouse/services/{svc['id']}/cost", headers=admin).json()
    c_other = client.get(f"/warehouse/services/{svc['id']}/cost", headers=other).json()
    assert (c_main["price"], c_main["net_price"]) == (100000, round(100000 * 100 / 112, 2))
    assert (c_other["price"], c_other["net_price"]) == (224000, 200000) and c_other["margin"] == 199000                     # filial narxidan foyda


def test_branch_price_permissions_validation_and_audit(client, auth, world):
    admin, other, b, svc = world
    sid = svc["id"]
    assert client.put(f"/services/{sid}/branch-price", json={"price": 1}, headers=auth("nurse")).status_code == 403
    assert client.put(f"/services/{sid}/branch-price", json={"price": -5}, headers=admin).status_code == 422
    assert client.put(f"/services/{sid}/branch-price", json={"price": 1.234}, headers=admin).status_code == 422
    assert client.put("/services/00000000-0000-0000-0000-000000000000/branch-price", json={"price": 5}, headers=admin).status_code == 404
    assert client.put(f"/services/{sid}/branch-price", json={"price": 0}, headers=admin).status_code == 200                # bepul (0) ruxsat
    assert client.get(f"/services/{sid}/branch-prices", headers=auth("cashier")).status_code == 200
    assert client.get("/services", headers=auth("cashier")).json()[0]["effective_price"] is not None
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import AuditLog
    with SessionLocal() as db:
        rows = db.scalars(select(AuditLog).where(AuditLog.entity_type == "service_branch_price")).all()
        assert len(rows) == 1 and rows[0].details["price"]["to"] == "0.00" or rows[0].details["price"]["to"] == "0"
