"""Bemor polislari va kafolat xatlari (v1.9.25): polis muddati, shartnoma bilan bog'lanish, kafolat xati limiti/muddati/holati, fayl ilovasi."""
import io
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AuditLog
from tests.test_patients import NEW

ZERO = "00000000-0000-0000-0000-000000000000"
PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
D = lambda n: (date.today() + timedelta(days=n)).isoformat()   # noqa: E731


@pytest.fixture
def world(client, auth):
    admin = auth("admin")
    ins = client.post("/insurance/insurers", json={"name": "Polis Kompaniyasi"}, headers=admin).json()
    svc = client.post("/services", headers=admin, json={"name": "Polis xizmati", "price": 100000, "mxik": "09302001001000000", "package_code": "1500364",
                                                       "vat_percent": 12}).json()["id"]
    contract = client.post("/insurance/contracts", headers=admin, json={"insurer_id": ins["id"], "number": "C-1", "valid_from": D(-100), "valid_to": D(200),
                                                                         "services": [{"service_id": svc, "coverage_percent": 100}]}).json()
    pid = client.post("/patients", json={**NEW, "name": "Polis Bemor"}, headers=admin).json()["id"]
    return admin, ins, contract, svc, pid


def _policy(client, h, pid, contract, number="POL-1", **kw):
    return client.post(f"/patients/{pid}/policies", headers=h, json={"contract_id": contract["id"], "number": number, "valid_from": D(-30), "valid_to": D(300), **kw})


def test_policy_create_validation_search_and_validity(client, auth, world):
    admin, ins, contract, svc, pid = world
    rec = auth("receptionist")
    res = _policy(client, rec, pid, contract)                                                              # qabulxona polis kiritadi (insurance:write)
    assert res.status_code == 201, res.text
    p = res.json()
    assert p["insurer"] == "Polis Kompaniyasi" and p["contract"] == "C-1" and p["valid_now"] is True and p["patient"] == "Polis Bemor"
    assert _policy(client, admin, pid, contract).status_code == 409                                          # raqam kompaniya ichida noyob
    assert client.post(f"/patients/{pid}/policies", headers=admin, json={"contract_id": ZERO, "number": "X", "valid_from": D(0)}).status_code == 422
    assert client.post(f"/patients/{pid}/policies", headers=admin, json={"contract_id": contract["id"], "number": "X", "valid_from": D(10), "valid_to": D(0)}).status_code == 422
    assert client.post(f"/patients/{ZERO}/policies", headers=admin, json={"contract_id": contract["id"], "number": "Y", "valid_from": D(0)}).status_code == 404
    assert _policy(client, auth("cashier"), pid, contract, "POL-C").status_code == 403                      # kassirda insurance:write yo'q
    expired = _policy(client, admin, pid, contract, "POL-OLD", valid_from=D(-400), valid_to=D(-10)).json()
    assert expired["valid_now"] is False
    assert [x["number"] for x in client.get(f"/patients/{pid}/policies", params={"valid_only": True}, headers=admin).json()] == ["POL-1"]
    assert {x["number"] for x in client.get(f"/patients/{pid}/policies", headers=admin).json()} == {"POL-1", "POL-OLD"}
    assert [x["number"] for x in client.get("/insurance/policies", params={"number": "pol-1"}, headers=admin).json()] == ["POL-1"]
    assert client.get("/insurance/policies", params={"patient_id": pid, "insurer_id": ins["id"]}, headers=auth("cashier")).status_code == 200
    off = client.put(f"/insurance/policies/{p['id']}", json={"is_active": False}, headers=rec).json()
    assert off["is_active"] is False and off["valid_now"] is False
    assert client.put(f"/insurance/policies/{p['id']}", json={"valid_to": D(-100)}, headers=admin).status_code == 422
    assert client.put(f"/insurance/policies/{ZERO}", json={"notes": "x"}, headers=admin).status_code == 404
    # faolsiz shartnomaga yangi polis yo'q; shartnoma tugagach polis amal qilmaydi
    client.put(f"/insurance/contracts/{contract['id']}", json={"is_active": False}, headers=admin)
    assert _policy(client, admin, pid, contract, "POL-NEW").status_code == 422
    assert client.get(f"/patients/{pid}/policies", params={"valid_only": True}, headers=admin).json() == []


def test_guarantee_letter_lifecycle_limits_services_and_state(client, auth, world):
    admin, ins, contract, svc, pid = world
    pol = _policy(client, admin, pid, contract).json()
    rec = auth("receptionist")
    body = {"policy_id": pol["id"], "number": "GL-1", "letter_date": D(0), "amount_limit": 2_000_000, "valid_from": D(0), "valid_to": D(60), "service_ids": [svc],
            "notes": "ambulator davolanish"}
    res = client.post("/insurance/guarantee-letters", json=body, headers=rec)
    assert res.status_code == 201, res.text
    g = res.json()
    assert g["amount_limit"] == 2_000_000 and g["used_amount"] == 0 and g["remaining"] == 2_000_000 and g["state"] == "Active" and g["status"] == "Active"
    assert g["policy_number"] == "POL-1" and g["patient"] == "Polis Bemor" and [s["service"] for s in g["services"]] == ["Polis xizmati"] and g["has_file"] is False
    assert client.post("/insurance/guarantee-letters", json=body, headers=admin).status_code == 409                          # raqam kompaniya ichida noyob
    for extra, code in (({"number": "GL-2", "amount_limit": 0}, 422), ({"number": "GL-3", "valid_to": D(-5)}, 422), ({"number": "GL-4", "policy_id": ZERO}, 422),
                        ({"number": "GL-5", "service_ids": [ZERO]}, 422), ({"number": "GL-6", "service_ids": [svc, svc]}, 422)):
        assert client.post("/insurance/guarantee-letters", json={**body, **extra}, headers=admin).status_code == code, extra
    client.put(f"/insurance/policies/{pol['id']}", json={"is_active": False}, headers=admin)
    assert client.post("/insurance/guarantee-letters", json={**body, "number": "GL-7"}, headers=admin).status_code == 422     # polis amal qilmasa xat yo'q
    client.put(f"/insurance/policies/{pol['id']}", json={"is_active": True}, headers=admin)
    assert client.post("/insurance/guarantee-letters", json=body, headers=auth("cashier")).status_code == 403
    # o'zgartirish
    upd = client.put(f"/insurance/guarantee-letters/{g['id']}", headers=rec, json={"amount_limit": 3_000_000, "service_ids": []})
    assert upd.status_code == 200 and upd.json()["amount_limit"] == 3_000_000 and upd.json()["services"] == []
    # holat: muddati o'tgan
    past = client.post("/insurance/guarantee-letters", headers=admin, json={**body, "number": "GL-OLD", "valid_from": D(-60), "valid_to": D(-1)}).json()
    assert past["state"] == "Expired"
    assert {x["number"] for x in client.get("/insurance/guarantee-letters", params={"state": "Active"}, headers=admin).json()} == {"GL-1"}
    assert {x["number"] for x in client.get("/insurance/guarantee-letters", params={"patient_id": pid}, headers=admin).json()} == {"GL-1", "GL-OLD"}
    assert client.get("/insurance/guarantee-letters", params={"number": "gl-old"}, headers=admin).json()[0]["id"] == past["id"]
    # bekor qilish
    assert client.post(f"/insurance/guarantee-letters/{g['id']}/cancel", json={"reason": "x"}, headers=admin).status_code == 422
    can = client.post(f"/insurance/guarantee-letters/{g['id']}/cancel", json={"reason": "kompaniya qaytarib oldi"}, headers=rec)
    assert can.status_code == 200 and can.json()["state"] == "Cancelled" and can.json()["cancel_reason"] == "kompaniya qaytarib oldi"
    assert client.post(f"/insurance/guarantee-letters/{g['id']}/cancel", json={"reason": "yana"}, headers=admin).status_code == 409
    assert client.put(f"/insurance/guarantee-letters/{g['id']}", json={"notes": "z"}, headers=admin).status_code == 409
    assert client.get(f"/insurance/guarantee-letters/{ZERO}", headers=admin).status_code == 404
    assert client.delete(f"/insurance/guarantee-letters/{g['id']}", headers=admin).status_code == 405


def test_guarantee_letter_file_upload_download_validation_and_audit(client, auth, world):
    admin, ins, contract, svc, pid = world
    pol = _policy(client, admin, pid, contract).json()
    g = client.post("/insurance/guarantee-letters", headers=admin, json={"policy_id": pol["id"], "number": "GL-F", "letter_date": D(0), "amount_limit": 500000}).json()
    url = f"/insurance/guarantee-letters/{g['id']}/file"
    assert client.get(url, headers=admin).status_code == 404                                                  # fayl hali yo'q
    assert client.post(url, files={"file": ("xat.pdf", io.BytesIO(b""), "application/pdf")}, headers=admin).status_code == 422
    assert client.post(url, files={"file": ("xat.exe", io.BytesIO(b"MZ" + b"\x00" * 50), "application/octet-stream")}, headers=admin).status_code == 415
    assert client.post(url, files={"file": ("xat.pdf", io.BytesIO(PDF), "application/pdf")}, headers=auth("cashier")).status_code == 403
    up = client.post(url, files={"file": ("../xat skan.pdf", io.BytesIO(PDF), "application/pdf")}, headers=auth("receptionist"))
    assert up.status_code == 200 and up.json()["has_file"] is True and up.json()["file_size"] == len(PDF) and "/" not in up.json()["file_name"]
    dl = client.get(url, headers=auth("cashier"))
    assert dl.status_code == 200 and dl.content == PDF and dl.headers["content-type"] == "application/pdf" and dl.headers["x-content-type-options"] == "nosniff"
    repl = client.post(url, files={"file": ("skan.png", io.BytesIO(PNG), "image/png")}, headers=admin).json()                 # almashtiriladi
    assert repl["file_name"].endswith(".png") and client.get(url, headers=admin).content == PNG
    assert client.get(url, headers=auth("doctor")).status_code == 403
    with SessionLocal() as db:
        rows = db.scalars(select(AuditLog).where(AuditLog.entity_type == "guarantee_letter")).all()
        assert any(r.action == "read" and r.details.get("download") for r in rows) and any(r.details.get("file") for r in rows)
