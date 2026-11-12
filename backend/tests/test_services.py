import pytest

from app.schemas.services import ServiceIn

GOOD = {"name": "Terapevt konsultatsiyasi", "price": 150000, "mxik": "09302001001000000", "package_code": "1500364", "vat_percent": 0}


def test_mxik_validation_formats(client, auth):
    admin = auth("admin")
    for bad in ("0930200100100000", "093020010010000000", "0930200100100000a", "abcdefghijklmnopq", "123"):   # 16, 18, harf, qisqa
        res = client.post("/services", headers=admin, json={**GOOD, "name": f"X {bad}", "mxik": bad})
        assert res.status_code == 422 and "MXIK" in res.text, bad
    ok = client.post("/services", headers=admin, json={**GOOD, "mxik": "0930 2001-0010 0000 0"})                     # bo'sh joy/chiziqcha tozalanadi
    assert ok.status_code == 201 and ok.json()["mxik"] == "09302001001000000"
    for bad in ("12345678901", "15a"):
        assert client.post("/services", headers=admin, json={**GOOD, "name": f"P {bad}", "package_code": bad}).status_code == 422, bad
    for bad in (-1, 101):
        assert client.post("/services", headers=admin, json={**GOOD, "name": f"V {bad}", "vat_percent": bad}).status_code == 422
    assert client.post("/services", headers=admin, json={**GOOD, "name": "Manfiy narx", "price": -5}).status_code == 422
    assert client.post("/services", headers=admin, json={**GOOD, "name": "Ko'p kasr", "price": 10.123}).status_code == 422
    with pytest.raises(ValueError):
        ServiceIn(**{**GOOD, "mxik": "1" * 16})


def test_service_without_codes_is_saved_but_not_sellable(client, auth):
    admin = auth("admin")
    bare = client.post("/services", headers=admin, json={"name": "Kodsiz xizmat", "price": 50000}).json()
    assert bare["sellable"] is False and bare["missing"] == ["mxik", "package_code", "vat_percent"]
    partial = client.post("/services", headers=admin, json={"name": "Qisman", "price": 1, "mxik": "09302001001000000"}).json()
    assert partial["sellable"] is False and partial["missing"] == ["package_code", "vat_percent"]
    full = client.post("/services", headers=admin, json=GOOD).json()
    assert full["sellable"] is True and full["missing"] == [] and full["vat_percent"] == 0.0     # 0 QQS to'g'ri qiymat (null emas)
    assert {s["name"] for s in client.get("/services", params={"sellable": True}, headers=admin).json()} == {GOOD["name"]}
    assert {s["name"] for s in client.get("/services", params={"sellable": False}, headers=admin).json()} == {"Kodsiz xizmat", "Qisman"}
    # kod to'ldirilsa sotiladigan bo'ladi
    fixed = client.put(f"/services/{bare['id']}", headers=admin, json={"mxik": "09302001001000001", "package_code": "1500364", "vat_percent": 12})
    assert fixed.json()["sellable"] is True
    # faolsizlantirilsa sotilmaydi
    off = client.put(f"/services/{bare['id']}", headers=admin, json={"is_active": False}).json()
    assert off["sellable"] is False and bare["name"] not in [s["name"] for s in client.get("/services", headers=admin).json()]
    assert bare["name"] in [s["name"] for s in client.get("/services", params={"include_inactive": True}, headers=admin).json()]


def test_money_is_numeric_and_clearing_codes(client, auth):
    admin = auth("admin")
    s = client.post("/services", headers=admin, json={**GOOD, "price": 123456.78}).json()
    assert s["price"] == 123456.78
    from sqlalchemy import text

    from app.db.session import SessionLocal
    with SessionLocal() as db:
        assert db.execute(text("select pg_typeof(price)::text from services limit 1")).scalar() == "numeric"
    cleared = client.put(f"/services/{s['id']}", headers=admin, json={"mxik": None}).json()
    assert cleared["mxik"] is None and cleared["sellable"] is False


def test_categories_filters_permissions_and_audit(client, auth):
    admin, cashier, doctor = auth("admin"), auth("cashier"), auth("doctor")
    cat = client.post("/service-categories", headers=admin, json={"name": "Konsultatsiya"}).json()
    assert client.post("/service-categories", headers=admin, json={"name": "konsultatsiya"}).status_code == 409
    svc = client.post("/services", headers=admin, json={**GOOD, "category_id": cat["id"]}).json()
    assert svc["category"] == "Konsultatsiya"
    client.post("/services", headers=admin, json={**GOOD, "name": "Boshqa"})
    assert [s["name"] for s in client.get("/services", params={"category_id": cat["id"]}, headers=cashier).json()] == [GOOD["name"]]
    assert [s["name"] for s in client.get("/services", params={"search": "bosh"}, headers=doctor).json()] == ["Boshqa"]
    assert client.post("/services", headers=cashier, json={**GOOD, "name": "Kassir qo'shdi"}).status_code == 403       # services:write faqat admin
    assert client.put(f"/services/{svc['id']}", headers=doctor, json={"price": 1}).status_code == 403
    assert client.get("/services", headers=auth("nurse")).status_code == 403
    assert client.post("/services", headers=admin, json={**GOOD, "category_id": "00000000-0000-0000-0000-000000000000",
                                                         "name": "Yo'q kategoriya"}).status_code == 422
    assert client.post("/services", headers=admin, json=GOOD).status_code == 409                                          # nom takrori
    client.put(f"/services/{svc['id']}", headers=admin, json={"price": 175000})
    audit = client.get("/security/audit", params={"entity_type": "service", "limit": 20}, headers=admin).json()["items"]
    upd = [e for e in audit if e["action"] == "update"][0]
    assert upd["details"]["changes"]["price"]["to"] == "175000.00" or "175000" in upd["details"]["changes"]["price"]["to"]
