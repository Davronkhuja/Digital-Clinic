"""Filiallar orasida ko'chirish hujjati (v1.9.9): yuborish (FEFO), qabul, bekor, jurnal yaxlitligi."""
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import AuditLog, StockBatch, StockMovement
from tests.conftest import login

ZERO = "00000000-0000-0000-0000-000000000000"


def _on(h, bid):
    return {**h, "X-Branch-Id": bid}


@pytest.fixture
def world(client, auth):
    """Asosiy filial (ombor to'ldirilgan) va ikkinchi filial (o'z hamshirasi bilan)."""
    admin = auth("admin")
    b = client.post("/branches", json={"name": "Qabul filiali"}, headers=admin).json()
    client.post("/users", headers=admin, json={"name": "Qabul Hamshira", "email": "recv@clinic.uz", "password": "password123", "role": "nurse",
                                                "branch_id": b["id"]})
    recv = {"Authorization": f"Bearer {login(client, email='recv@clinic.uz')['access_token']}"}
    item = client.post("/warehouse/items", json={"name": "Ko'chiriladigan", "unit": "dona"}, headers=admin).json()["id"]
    lines = [{"item_id": item, "batch_no": n, "qty": q, "unit_cost": c, "expires_on": (date.today() + timedelta(days=d)).isoformat()}
             for n, q, c, d in (("LATE", 30, 120, 300), ("SOON", 10, 100, 20), ("MID", 20, 110, 90))]
    assert client.post("/warehouse/receipts", json={"lines": lines}, headers=admin).status_code == 201
    return admin, auth("nurse"), recv, b["id"], item


def _send(client, h, to, item, qty, notes=None):
    return client.post("/warehouse/transfers", headers=h, json={"to_branch_id": to, "notes": notes, "lines": [{"item_id": item, "qty": qty}]})


def _qty(client, h):
    return client.get("/warehouse/stock", headers=h).json()[0]["qty"]


def test_send_takes_fefo_from_source_and_receive_creates_batches_in_destination(client, world):
    admin, nurse, recv, bid, item = world
    res = _send(client, nurse, bid, item, 35, "haftalik")
    assert res.status_code == 201, res.text
    t = res.json()
    assert t["status"] == "Sent" and t["number"].startswith("TR-") and t["to_branch"] == "Qabul filiali" and t["notes"] == "haftalik"
    assert [(ln["batch_no"], ln["qty"]) for ln in t["lines"]] == [("SOON", 10), ("MID", 20), ("LATE", 5)]       # FEFO (muddat bo'yicha)
    assert t["total"] == 10 * 100 + 20 * 110 + 5 * 120
    assert _qty(client, nurse) == 25 and _qty(client, recv) == 0                    # yo'lda: manba kamaydi, qabul qiluvchida hali yo'q
    assert [x["id"] for x in client.get("/warehouse/transfers", params={"direction": "out"}, headers=nurse).json()] == [t["id"]]
    assert [x["id"] for x in client.get("/warehouse/transfers", params={"direction": "in"}, headers=recv).json()] == [t["id"]]
    assert client.get("/warehouse/transfers", params={"direction": "in"}, headers=nurse).json() == []
    assert client.post(f"/warehouse/transfers/{t['id']}/receive", headers=nurse).status_code == 403             # yuboruvchi qabul qila olmaydi
    done = client.post(f"/warehouse/transfers/{t['id']}/receive", headers=recv)
    assert done.status_code == 200 and done.json()["status"] == "Received" and done.json()["received_at"]
    assert _qty(client, recv) == 35 and _qty(client, nurse) == 25
    got = client.get("/warehouse/batches", headers=recv).json()
    assert [(b["batch_no"], b["qty_remaining"], b["unit_cost"], b["expires_on"]) for b in got] == [
        ("SOON", 10, 100, (date.today() + timedelta(days=20)).isoformat()), ("MID", 20, 110, (date.today() + timedelta(days=90)).isoformat()),
        ("LATE", 5, 120, (date.today() + timedelta(days=300)).isoformat())]                              # partiya raqami, muddat, narx saqlandi
    assert client.post(f"/warehouse/transfers/{t['id']}/receive", headers=recv).status_code == 409           # ikki marta qabul qilinmaydi
    assert client.post(f"/warehouse/transfers/{t['id']}/cancel", headers=nurse, json={"reason": "kech"}).status_code == 409
    kinds = {m["kind"] for m in client.get("/warehouse/movements", headers=recv).json()}
    assert kinds == {"TransferIn"} and "TransferOut" in {m["kind"] for m in client.get("/warehouse/movements", headers=nurse).json()}


def test_cancel_returns_stock_to_source_batches(client, world):
    admin, nurse, recv, bid, item = world
    t = _send(client, nurse, bid, item, 35).json()
    assert client.post(f"/warehouse/transfers/{t['id']}/cancel", headers=recv, json={"reason": "men emasman"}).status_code == 403
    assert client.post(f"/warehouse/transfers/{t['id']}/cancel", headers=nurse, json={"reason": "x"}).status_code == 422
    out = client.post(f"/warehouse/transfers/{t['id']}/cancel", headers=nurse, json={"reason": "noto'g'ri filial"})
    assert out.status_code == 200 and out.json()["status"] == "Cancelled" and out.json()["cancel_reason"] == "noto'g'ri filial"
    assert _qty(client, nurse) == 60 and _qty(client, recv) == 0
    assert {b["batch_no"]: b["qty_remaining"] for b in client.get("/warehouse/batches", headers=nurse).json()} == {"SOON": 10, "MID": 20, "LATE": 30}
    assert client.post(f"/warehouse/transfers/{t['id']}/receive", headers=recv).status_code == 409                 # bekor qilinganni qabul qilib bo'lmaydi
    again = _send(client, nurse, bid, item, 35).json()                                                            # qayta yuborish mumkin, FEFO yana avvalgidek
    assert [ln["batch_no"] for ln in again["lines"]] == ["SOON", "MID", "LATE"] and again["number"] != t["number"]


def test_validation_permissions_and_visibility(client, auth, world):
    admin, nurse, recv, bid, item = world
    main_id = next(x["id"] for x in client.get("/branches", headers=admin).json() if x["is_default"])
    assert _send(client, nurse, main_id, item, 1).status_code == 422                                              # o'ziga
    assert _send(client, nurse, ZERO, item, 1).status_code == 422
    assert _send(client, nurse, bid, item, 61).status_code == 409                                                 # yetmaydi
    assert _qty(client, nurse) == 60                                                                              # hech narsa o'zgarmadi
    assert _send(client, nurse, bid, item, 0).status_code == 422
    assert _send(client, nurse, bid, "00000000-0000-0000-0000-000000000000", 1).status_code == 422
    assert client.post("/warehouse/transfers", headers=nurse, json={"to_branch_id": bid, "lines": []}).status_code == 422
    assert _send(client, auth("doctor"), bid, item, 1).status_code == 403
    assert client.get("/warehouse/transfers", headers=auth("cashier")).status_code == 403
    third = client.post("/branches", json={"name": "Uchinchi"}, headers=admin).json()["id"]
    t = _send(client, nurse, bid, item, 5).json()
    assert client.get(f"/warehouse/transfers/{t['id']}", headers=_on(admin, third)).status_code == 404            # aloqasiz filial ko'rmaydi
    assert client.post(f"/warehouse/transfers/{t['id']}/receive", headers=_on(admin, third)).status_code == 404
    assert client.get(f"/warehouse/transfers/{t['id']}", headers=recv).json()["id"] == t["id"]
    assert client.get(f"/warehouse/transfers/{ZERO}", headers=nurse).status_code == 404
    dup = client.post("/warehouse/transfers", headers=nurse, json={"to_branch_id": bid, "lines": [{"item_id": item, "qty": 3}, {"item_id": item, "qty": 4}]}).json()
    assert sum(ln["qty"] for ln in dup["lines"]) == 7                                                              # bir material ikki qatorda: yig'iladi
    client.put(f"/branches/{third}", json={"is_active": False}, headers=admin)
    assert _send(client, nurse, third, item, 1).status_code == 422                                                 # faolsiz filialga


def test_ledger_integrity_and_audit_after_transfers(client, world):
    admin, nurse, recv, bid, item = world
    t1 = _send(client, nurse, bid, item, 35).json()
    client.post(f"/warehouse/transfers/{t1['id']}/receive", headers=recv)
    t2 = _send(client, nurse, bid, item, 10).json()
    client.post(f"/warehouse/transfers/{t2['id']}/cancel", headers=nurse, json={"reason": "qayta o'ylandi"})
    with SessionLocal() as db:
        for b in db.scalars(select(StockBatch)):                                           # har partiya: harakatlar yig'indisi = qoldiq
            assert db.scalar(select(func.coalesce(func.sum(StockMovement.qty), 0)).where(StockMovement.batch_id == b.id)) == b.qty_remaining
        total = db.scalar(select(func.sum(StockBatch.qty_remaining)))
        assert total == 60                                                                 # ko'chirishda moddiy qiymat yo'qolmaydi
        acts = {(r.action, r.details.get("status")) for r in db.scalars(select(AuditLog).where(AuditLog.entity_type == "stock_transfer"))}
        assert acts == {("create", None), ("update", "Received"), ("update", "Cancelled")}
