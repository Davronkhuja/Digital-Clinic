"""Filiallar (v1.9.6): boshqaruv, faol filialni almashtirish (X-Branch-Id), foydalanuvchini filialga biriktirish, filial bo'yicha ombor."""
from datetime import date, timedelta

from tests.conftest import login

ZERO = "00000000-0000-0000-0000-000000000000"


def _branch(client, h, name="Chilonzor filiali", **kw):
    res = client.post("/branches", json={"name": name, **kw}, headers=h)
    assert res.status_code == 201, res.text
    return res.json()


def _on(h, branch_id):
    return {**h, "X-Branch-Id": branch_id}


def _stock(client, h, item, qty, batch="B-1"):
    body = {"lines": [{"item_id": item, "batch_no": batch, "qty": qty, "unit_cost": 100, "expires_on": (date.today() + timedelta(days=90)).isoformat()}]}
    assert client.post("/warehouse/receipts", json=body, headers=h).status_code == 201


def test_create_branch_copies_settings_and_unique_name(client, auth):
    admin = auth("admin")
    b = _branch(client, admin, address="Chilonzor 5", phone="+998 71 200 00 00")
    assert b["is_default"] is False and b["is_active"] is True and b["users_count"] == 0 and b["current"] is False
    assert client.post("/branches", json={"name": "chilonzor FILIALI"}, headers=admin).status_code == 409
    main = client.get("/settings", headers=admin).json()
    other = client.get("/settings", headers=_on(admin, b["id"])).json()                  # yangi filial sozlamalari asosiydan nusxalangan
    assert other["clinic_name"] == main["clinic_name"] and other["address"] == "Chilonzor 5" and other["phone"] == "+998 71 200 00 00"
    assert client.post("/branches", json={"name": "Yo'q huquq"}, headers=auth("nurse")).status_code == 403
    assert client.post("/branches", json={"name": "x"}, headers=admin).status_code == 422
    listed = client.get("/branches", headers=admin).json()
    assert [x["name"] for x in listed][0] != b["name"] and {x["name"] for x in listed} >= {b["name"]}
    assert [x["current"] for x in listed].count(True) == 1


def test_branch_switching_requires_permission_and_valid_active_branch(client, auth):
    admin = auth("admin")
    b = _branch(client, admin)
    assert client.get("/branches", headers=_on(admin, b["id"])).json()[[x["id"] for x in client.get("/branches", headers=admin).json()].index(b["id"])]["current"] is True
    assert client.get("/auth/me", headers=_on(admin, b["id"])).json()["branch_id"] == b["id"]
    assert client.get("/auth/me", headers=admin).json()["branch_id"] != b["id"]
    nurse = auth("nurse")
    assert client.get("/branches", headers=nurse).json().__len__() == 1                   # xodim faqat o'z filialini ko'radi
    assert client.get("/warehouse/stock", headers=_on(nurse, b["id"])).status_code == 403
    assert client.get("/warehouse/stock", headers=_on(admin, "garbage")).status_code == 422
    assert client.get("/warehouse/stock", headers=_on(admin, ZERO)).status_code == 400
    assert client.put(f"/branches/{b['id']}", json={"is_active": False}, headers=_on(admin, b["id"])).status_code == 409     # faol filialni o'zi o'chirmaydi
    assert client.put(f"/branches/{b['id']}", json={"is_active": False}, headers=admin).status_code == 200
    assert client.get("/warehouse/stock", headers=_on(admin, b["id"])).status_code == 400          # faolsiz filialga o'tib bo'lmaydi
    assert b["id"] not in [x["id"] for x in client.get("/branches", headers=admin).json()]
    assert b["id"] in [x["id"] for x in client.get("/branches", params={"include_inactive": True}, headers=admin).json()]


def test_warehouse_stock_is_per_branch_but_catalog_is_shared(client, auth):
    admin = auth("admin")
    b = _branch(client, admin)
    item = client.post("/warehouse/items", json={"name": "Umumiy material", "unit": "dona"}, headers=admin).json()["id"]
    _stock(client, admin, item, 10, "A-1")
    _stock(client, _on(admin, b["id"]), item, 3, "B-1")
    here = client.get("/warehouse/stock", headers=admin).json()[0]
    there = client.get("/warehouse/stock", headers=_on(admin, b["id"])).json()[0]
    assert (here["qty"], there["qty"]) == (10, 3) and here["item_id"] == there["item_id"]                # katalog umumiy, qoldiq alohida
    assert [x["batch_no"] for x in client.get("/warehouse/batches", headers=_on(admin, b["id"])).json()] == ["B-1"]
    assert client.post("/warehouse/issues", json={"item_id": item, "qty": 5, "reason": "tekshiruv"}, headers=_on(admin, b["id"])).status_code == 409   # 3 bor
    assert client.post("/warehouse/issues", json={"item_id": item, "qty": 5, "reason": "tekshiruv"}, headers=admin).status_code == 200
    assert len(client.get("/warehouse/movements", headers=_on(admin, b["id"])).json()) == 1
    receipts = client.get("/warehouse/receipts", headers=_on(admin, b["id"])).json()
    assert len(receipts) == 1 and client.get(f"/warehouse/receipts/{client.get('/warehouse/receipts', headers=admin).json()[0]['id']}",
                                             headers=_on(admin, b["id"])).status_code == 404           # boshqa filial hujjati ko'rinmaydi


def test_users_belong_to_a_branch_and_can_be_moved(client, auth):
    admin = auth("admin")
    b = _branch(client, admin)
    made = client.post("/users", headers=admin, json={"name": "Filial Hamshira", "email": "filial.nurse@clinic.uz", "password": "password123",
                                                       "role": "nurse", "branch_id": b["id"]})
    assert made.status_code == 201 and made.json()["branch_id"] == b["id"] and made.json()["branch"] == b["name"]
    uid = made.json()["id"]
    assert client.get("/branches", headers=admin).json()[-1]["users_count"] == 1
    h = {"Authorization": f"Bearer {login(client, email='filial.nurse@clinic.uz')['access_token']}"}
    assert client.get("/auth/me", headers=h).json()["branch_id"] == b["id"]
    item = client.post("/warehouse/items", json={"name": "Filial material", "unit": "dona"}, headers=admin).json()["id"]
    _stock(client, _on(admin, b["id"]), item, 7)
    assert client.get("/warehouse/stock", headers=h).json()[0]["qty"] == 7                         # xodim o'z filialining omborini ko'radi
    main_id = next(x["id"] for x in client.get("/branches", headers=admin).json() if x["is_default"])
    assert client.get("/warehouse/stock", headers=auth("nurse")).json()[0]["qty"] == 0
    assert client.patch(f"/users/{uid}", json={"branch_id": main_id}, headers=admin).json()["branch_id"] == main_id        # ko'chirildi
    assert client.get("/warehouse/stock", headers=h).json()[0]["qty"] == 0                          # token o'sha, filial yangi (har so'rovda o'qiladi)
    assert client.post("/users", headers=admin, json={"name": "X Y", "email": "x.y@clinic.uz", "password": "password123", "role": "nurse",
                                                      "branch_id": ZERO}).status_code == 422
    assert client.patch(f"/users/{uid}", json={"branch_id": "garbage"}, headers=admin).status_code == 422


def test_deactivation_rules_and_audit(client, auth):
    admin = auth("admin")
    main_id = next(x["id"] for x in client.get("/branches", headers=admin).json() if x["is_default"])
    assert client.put(f"/branches/{main_id}", json={"is_active": False}, headers=_on(admin, _branch(client, admin, "Vaqtincha")["id"])).status_code == 409
    b = _branch(client, admin)
    client.post("/users", headers=admin, json={"name": "Filial Kassir", "email": "filial.k@clinic.uz", "password": "password123", "role": "cashier",
                                               "branch_id": b["id"]})
    r = client.put(f"/branches/{b['id']}", json={"is_active": False}, headers=admin)
    assert r.status_code == 409 and "xodim" in r.json()["detail"]
    uid = next(u["id"] for u in client.get("/users", headers=admin).json() if u["email"] == "filial.k@clinic.uz")
    client.patch(f"/users/{uid}", json={"branch_id": main_id}, headers=admin)
    item = client.post("/warehouse/items", json={"name": "Qoldiq", "unit": "dona"}, headers=admin).json()["id"]
    _stock(client, _on(admin, b["id"]), item, 2)
    r = client.put(f"/branches/{b['id']}", json={"is_active": False}, headers=admin)
    assert r.status_code == 409 and "qoldiq" in r.json()["detail"]
    client.post("/warehouse/issues", json={"item_id": item, "qty": 2, "reason": "bo'shatish"}, headers=_on(admin, b["id"]))
    assert client.put(f"/branches/{b['id']}", json={"is_active": False}, headers=admin).status_code == 200
    assert client.put(f"/branches/{ZERO}", json={"name": "Yo'q"}, headers=admin).status_code == 404
    assert client.put(f"/branches/{main_id}", json={"name": b["name"]}, headers=admin).status_code == 409           # nom takrorlanmaydi
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import AuditLog
    with SessionLocal() as db:
        acts = {(r.action, r.entity_type) for r in db.scalars(select(AuditLog).where(AuditLog.entity_type == "branch"))}
        assert acts == {("create", "branch"), ("update", "branch")}
