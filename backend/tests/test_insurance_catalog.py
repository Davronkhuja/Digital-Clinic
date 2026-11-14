"""Sug'urta katalogi (v1.9.24): kompaniyalar, shartnomalar (muddat, chegirma, qoplanadigan xizmatlar, limitlar), ruxsatlar."""
import pytest

ZERO = "00000000-0000-0000-0000-000000000000"
SERVICE = {"price": 100000, "mxik": "09302001001000000", "package_code": "1500364", "vat_percent": 12}


def _insurer(client, h, name="Kapital Sug'urta", **kw):
    res = client.post("/insurance/insurers", json={"name": name, **kw}, headers=h)
    assert res.status_code == 201, res.text
    return res.json()


def _service(client, h, name):
    return client.post("/services", headers=h, json={**SERVICE, "name": name}).json()["id"]


def _contract(client, h, insurer_id, number="DMS-2026/1", **kw):
    body = {"insurer_id": insurer_id, "number": number, "valid_from": "2026-01-01", "valid_to": "2026-12-31", **kw}
    return client.post("/insurance/contracts", json=body, headers=h)


def test_insurer_crud_uniqueness_permissions(client, auth):
    admin = auth("admin")
    ins = _insurer(client, admin, tin="123456789", phone="+998 71 100 00 00", payment_days=45, contact_person="Aziz")
    assert ins["payment_days"] == 45 and ins["contracts"] == 0 and ins["is_active"] is True
    assert client.post("/insurance/insurers", json={"name": "kapital SUG'URTA"}, headers=admin).status_code == 409             # registrsiz noyob
    assert client.post("/insurance/insurers", json={"name": "x"}, headers=admin).status_code == 422
    assert client.post("/insurance/insurers", json={"name": "Yangi", "payment_days": -1}, headers=admin).status_code == 422
    other = _insurer(client, admin, "Ipak Yo'li Sug'urta")
    assert client.put(f"/insurance/insurers/{other['id']}", json={"name": "KAPITAL sug'urta"}, headers=admin).status_code == 409
    upd = client.put(f"/insurance/insurers/{other['id']}", json={"payment_days": 10, "is_active": False}, headers=admin).json()
    assert upd["payment_days"] == 10 and upd["is_active"] is False
    assert [i["name"] for i in client.get("/insurance/insurers", headers=admin).json()] == ["Kapital Sug'urta"]               # faolsiz yashirin
    assert len(client.get("/insurance/insurers", params={"include_inactive": True}, headers=admin).json()) == 2
    assert client.put(f"/insurance/insurers/{ZERO}", json={"notes": "x"}, headers=admin).status_code == 404
    assert client.delete(f"/insurance/insurers/{ins['id']}", headers=admin).status_code == 405                                # o'chirilmaydi
    assert client.post("/insurance/insurers", json={"name": "Ruxsatsiz"}, headers=auth("receptionist")).status_code == 403    # insurance:manage faqat admin
    assert client.get("/insurance/insurers", headers=auth("receptionist")).status_code == 200
    assert client.get("/insurance/insurers", headers=auth("cashier")).status_code == 200
    assert client.get("/insurance/insurers", headers=auth("doctor")).status_code == 403


def test_contract_with_services_limits_and_validation(client, auth):
    admin = auth("admin")
    ins = _insurer(client, admin)
    a, b = _service(client, admin, "Konsultatsiya DMS"), _service(client, admin, "Tahlil DMS")
    res = _contract(client, admin, ins["id"], discount_percent=10, annual_limit=5_000_000, per_visit_limit=1_000_000, requires_guarantee=True,
                    services=[{"service_id": a, "coverage_percent": 100}, {"service_id": b, "coverage_percent": 80}])
    assert res.status_code == 201, res.text
    c = res.json()
    assert c["insurer"] == "Kapital Sug'urta" and c["discount_percent"] == 10 and c["annual_limit"] == 5_000_000 and c["per_visit_limit"] == 1_000_000
    assert c["requires_guarantee"] is True and c["coverage_all"] is False
    assert {s["service"]: s["coverage_percent"] for s in c["services"]} == {"Konsultatsiya DMS": 100, "Tahlil DMS": 80}
    assert client.get("/insurance/insurers", headers=admin).json()[0]["contracts"] == 1
    assert _contract(client, admin, ins["id"]).status_code == 409                                                             # raqam kompaniya ichida noyob
    assert _contract(client, admin, _insurer(client, admin, "Boshqa Kompaniya")["id"]).status_code == 201                   # boshqa kompaniyada bo'ladi
    bad = [({"valid_to": "2025-12-31"}, 422), ({"discount_percent": 101}, 422), ({"default_coverage_percent": 0}, 422), ({"annual_limit": -1}, 422),
           ({"coverage_all": True, "services": [{"service_id": a}]}, 422), ({"services": [{"service_id": a}, {"service_id": a}]}, 422),
           ({"services": [{"service_id": ZERO}]}, 422), ({"services": [{"service_id": a, "coverage_percent": 0}]}, 422)]
    for i, (extra, code) in enumerate(bad):
        assert _contract(client, admin, ins["id"], number=f"BAD-{i}", **extra).status_code == code, extra
    assert client.post("/insurance/contracts", json={"insurer_id": ZERO, "number": "Z", "valid_from": "2026-01-01"}, headers=admin).status_code == 422
    assert client.post("/insurance/contracts", json={"insurer_id": "garbage", "number": "Z", "valid_from": "2026-01-01"}, headers=admin).status_code == 422
    # o'zgartirish: xizmatlar almashtiriladi, chegirma o'zgaradi
    upd = client.put(f"/insurance/contracts/{c['id']}", headers=admin, json={"discount_percent": 15, "services": [{"service_id": b, "coverage_percent": 50}]})
    assert upd.status_code == 200 and upd.json()["discount_percent"] == 15 and [(s["service"], s["coverage_percent"]) for s in upd.json()["services"]] == [("Tahlil DMS", 50)]
    assert client.put(f"/insurance/contracts/{c['id']}", headers=admin, json={"valid_to": "2025-01-01"}).status_code == 422
    assert client.put(f"/insurance/contracts/{c['id']}", headers=admin, json={"coverage_all": True}).status_code == 200      # endi hamma xizmat: ro'yxat bo'lsa rad etilishi kerak
    assert client.put(f"/insurance/contracts/{c['id']}", headers=admin, json={"services": [{"service_id": a}]}).status_code == 422
    allc = client.put(f"/insurance/contracts/{c['id']}", headers=admin, json={"coverage_all": True, "services": [], "default_coverage_percent": 70}).json()
    assert allc["coverage_all"] is True and allc["services"] == [] and allc["default_coverage_percent"] == 70
    assert client.get(f"/insurance/contracts/{c['id']}", headers=admin).json()["default_coverage_percent"] == 70
    assert client.get(f"/insurance/contracts/{ZERO}", headers=admin).status_code == 404
    off = client.put(f"/insurance/contracts/{c['id']}", headers=admin, json={"is_active": False}).json()
    assert off["is_active"] is False and c["id"] not in [x["id"] for x in client.get("/insurance/contracts", headers=admin).json()]
    assert client.get("/insurance/contracts", params={"insurer_id": ins["id"], "include_inactive": True}, headers=admin).json()[0]["number"] == "DMS-2026/1"
    assert client.post("/insurance/contracts", json={"insurer_id": ins["id"], "number": "NO", "valid_from": "2026-01-01"}, headers=auth("receptionist")).status_code == 403
    inactive = _insurer(client, admin, "Faolsiz Kompaniya")
    client.put(f"/insurance/insurers/{inactive['id']}", json={"is_active": False}, headers=admin)
    assert _contract(client, admin, inactive["id"]).status_code == 422                                                         # faolsiz kompaniyaga yangi shartnoma yo'q


@pytest.mark.parametrize("role,code", [("admin", 200), ("cashier", 200), ("receptionist", 200), ("nurse", 403), ("doctor", 403)])
def test_read_permissions(client, auth, role, code):
    assert client.get("/insurance/contracts", headers=auth(role)).status_code == code
