"""Ombor mas'uliga bildirishnoma (v1.9.16): yetishmovchilik, minimal qoldiq, yaroqlilik; filial va ruxsat bo'yicha; takrorlanmaydi."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Notification
from app.services import notifications
from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")


def _item(client, h, name, min_qty=0):
    return client.post("/warehouse/items", json={"name": name, "unit": "dona", "min_qty": min_qty}, headers=h).json()["id"]


def _receive(client, h, item, qty, batch, days, cost=100):
    body = {"lines": [{"item_id": item, "batch_no": batch, "qty": qty, "unit_cost": cost, "expires_on": (date.today() + timedelta(days=days)).isoformat()}]}
    assert client.post("/warehouse/receipts", json=body, headers=h).status_code == 201


def _titles(client, h, **params):
    return [n["title"] for n in client.get("/notifications", params=params, headers=h).json()]


def test_shortage_on_perform_notifies_warehouse_staff_only(client, auth):
    admin = auth("admin")
    item = _item(client, admin, "Kam material")
    _receive(client, admin, item, 4, "K-1", 60)
    svc = client.post("/services", headers=admin, json={"name": "Katta sarf", "price": 112000, "mxik": "09302001001000000", "package_code": "1500364",
                                                       "vat_percent": 12}).json()["id"]
    client.put(f"/warehouse/services/{svc}/materials", headers=admin, json={"materials": [{"item_id": item, "qty": 3}]})
    pid = client.post("/patients", json={**NEW, "name": "Xabar Bemor"}, headers=admin).json()["id"]
    inv = client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "issue": True, "lines": [{"service_id": svc, "quantity": 2}]}).json()
    client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json={"method": "Cash"})
    assert client.get("/notifications/unread-count", headers=admin).json() == {"unread": 0}                       # to'lov xabar yaratmaydi
    assert client.post(f"/invoices/{inv['id']}/lines/{inv['lines'][0]['id']}/perform", headers=auth("doctor")).status_code == 200
    got = client.get("/notifications", headers=admin).json()
    assert {n["kind"] for n in got} == {"stock_shortage"} and got[0]["title"] == "Omborda yetmadi: Kam material" and inv["number"] in got[0]["body"]
    assert got[0]["link"] == "/warehouse" and got[0]["read"] is False
    assert _titles(client, auth("nurse")) == ["Omborda yetmadi: Kam material"]                                       # warehouse:write bor hamshira ham ko'radi
    assert client.get("/notifications", headers=auth("cashier")).json() == [] and client.get("/notifications", headers=auth("doctor")).json() == []


def test_read_state_is_per_user_and_mark_all(client, auth):
    admin, nurse = auth("admin"), auth("nurse")
    with SessionLocal() as db:
        from app.models import Branch
        bid = db.scalar(select(Branch.id).where(Branch.is_default.is_(True)))
        for i in range(3):
            notifications.notify(db, branch_id=bid, permission="warehouse:write", kind="stock_low", title=f"T{i}", dedupe_key=f"t{i}")
        db.commit()
    assert client.get("/notifications/unread-count", headers=admin).json()["unread"] == 3
    first = client.get("/notifications", headers=admin).json()[0]["id"]
    assert client.post(f"/notifications/{first}/read", headers=admin).json() == {"unread": 2}
    assert client.post(f"/notifications/{first}/read", headers=admin).json() == {"unread": 2}                       # takror: bir xil
    assert client.get("/notifications/unread-count", headers=nurse).json()["unread"] == 3                           # boshqa xodimga ta'sir qilmaydi
    assert len(client.get("/notifications", params={"unread_only": True}, headers=admin).json()) == 2
    assert client.post("/notifications/read-all", headers=admin).json() == {"unread": 0}
    assert client.post("/notifications/00000000-0000-0000-0000-000000000000/read", headers=admin).status_code == 404
    assert client.post(f"/notifications/{first}/read", headers=auth("cashier")).status_code == 404                  # ruxsati yo'q


def test_low_stock_after_issue_dedupe_and_branch_isolation(client, auth):
    admin = auth("admin")
    item = _item(client, admin, "Minimalli", min_qty=10)
    _receive(client, admin, item, 12, "M-1", 90)
    assert client.get("/notifications", headers=admin).json() == []
    client.post("/warehouse/issues", json={"item_id": item, "qty": 5, "reason": "protsedura"}, headers=admin)          # 7 < 10
    assert _titles(client, admin) == ["Minimal qoldiqdan kam: Minimalli"]
    client.post("/warehouse/issues", json={"item_id": item, "qty": 1, "reason": "yana"}, headers=admin)                # shu kunda takrorlanmaydi
    assert len(client.get("/notifications", headers=admin).json()) == 1
    other = client.post("/branches", json={"name": "Xabar filiali"}, headers=admin).json()["id"]
    assert client.get("/notifications", headers={**admin, "X-Branch-Id": other}).json() == []                         # boshqa filialga ko'rinmaydi


def test_daily_scan_expiring_expired_once_per_period(client, auth):
    admin = auth("admin")
    item = _item(client, admin, "Muddatli", min_qty=0)
    _receive(client, admin, item, 5, "SOON", 10)
    _receive(client, admin, item, 5, "OLD", 40)
    _receive(client, admin, item, 5, "FAR", 200)
    with SessionLocal() as db:
        from app.models import StockBatch
        db.scalar(select(StockBatch).where(StockBatch.batch_no == "OLD")).expires_on = date.today() - timedelta(days=3)
        db.commit()
        assert notifications.scan_all(db) == {"low": 0, "expiring": 1, "expired": 1}
        assert notifications.scan_all(db) == {"low": 0, "expiring": 0, "expired": 0}                                  # takroriy yurish yangi xabar yaratmaydi
    titles = _titles(client, admin)
    assert "Muddati 10 kunda tugaydi: Muddatli" in titles and "Muddati o'tgan: Muddatli" in titles and len(titles) == 2
    with SessionLocal() as db:
        assert len(db.scalars(select(Notification)).all()) == 2
