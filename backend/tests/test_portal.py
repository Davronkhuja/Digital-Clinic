import io
import re

import pytest
from pypdf import PdfReader

from app.services import messaging
from tests.test_patients import NEW
from tests.test_schedule import _day

DOC = "Dr. Behruz Rustamov"
PHONE = "+998 90 600 00 01"


@pytest.fixture(autouse=True)
def _clear():
    messaging.MockSmsAdapter.SENT.clear()


def _login(client, phone=PHONE):
    client.post("/public/otp/request", json={"phone": phone, "purpose": "portal"})
    code = re.search(r"\b(\d{6})\b", messaging.MockSmsAdapter.SENT[-1][1]).group(1)
    token = client.post("/public/otp/verify", json={"phone": phone, "purpose": "portal", "code": code}).json()["token"]
    return client.post("/portal/login", json={"token": token})


def _auth_header(res):
    return {"Authorization": "Bearer " + res.json()["session"]}


def _patient(client, auth, name="Portal Bemor", phone=PHONE):
    return client.post("/patients", json={**NEW, "name": name, "phone": phone}, headers=auth("admin")).json()["id"]


def test_login_lists_family_members_and_requires_session(client, auth):
    a, b = _patient(client, auth, "Ota Portal"), _patient(client, auth, "Bola Portal")
    _patient(client, auth, "Boshqa Telefon", "+998 90 600 00 02")
    res = _login(client)
    assert res.status_code == 200
    assert {p["id"] for p in res.json()["patients"]} == {a, b}
    assert client.get(f"/portal/{a}/appointments").status_code == 401
    assert client.get(f"/portal/{a}/appointments", headers={"Authorization": "Bearer xxx"}).status_code == 401
    assert client.post("/portal/login", json={"token": "garbage"}).status_code == 401
    # booking maqsadidagi token portalga yaramaydi
    client.post("/public/otp/request", json={"phone": PHONE, "purpose": "booking"})
    code = re.search(r"\b(\d{6})\b", messaging.MockSmsAdapter.SENT[-1][1]).group(1)
    wrong = client.post("/public/otp/verify", json={"phone": PHONE, "purpose": "booking", "code": code}).json()["token"]
    assert client.post("/portal/login", json={"token": wrong}).status_code == 401
    assert _login(client, "+998 90 600 09 99").status_code == 404                                  # bu telefonda bemor yo'q


def test_patients_cannot_see_each_others_data(client, auth):
    mine = _patient(client, auth, "Mening Bemorim")
    other = _patient(client, auth, "Begona Bemor", "+998 90 600 00 03")
    h = _auth_header(_login(client))
    for path in ("appointments", "invoices", "lab-results"):
        assert client.get(f"/portal/{mine}/{path}", headers=h).status_code == 200
        assert client.get(f"/portal/{other}/{path}", headers=h).status_code == 404
    assert client.get(f"/portal/{mine}/emr", headers=h).status_code == 404                        # EMR portalda yo'q


def test_appointments_confirm_cancel_and_waitlist_offer(client, auth):
    pid = _patient(client, auth)
    appt = client.post("/appointments", headers=auth("admin"), json={"patient_id": pid, "doctor": DOC, "date": _day(0), "time": "10:00", "type": "Konsultatsiya"}).json()
    waiter = _patient(client, auth, "Kutuvchi Portal", "+998 90 600 00 04")
    client.put(f"/patients/{waiter}/consents", headers=auth("admin"), json={"channel": "SMS", "granted": True})
    client.post("/waitlist", headers=auth("admin"), json={"patient_id": waiter, "doctor": DOC, "date_from": _day(0), "date_to": _day(0)})
    h = _auth_header(_login(client))
    rows = client.get(f"/portal/{pid}/appointments", headers=h).json()
    assert rows[0]["doctor"] == DOC and rows[0]["time"] == "10:00" and rows[0]["can_act"] is True and rows[0]["confirmed"] is False
    assert set(rows[0]) == {"id", "date", "time", "doctor", "branch_id", "branch", "type", "status", "confirmed", "can_act"}      # tibbiy ma'lumot yo'q
    assert client.post(f"/portal/{pid}/appointments/{appt['id']}/confirm", headers=h).json() == {"confirmed": True}
    assert client.get(f"/portal/{pid}/appointments", headers=h).json()[0]["confirmed"] is True
    assert client.post(f"/portal/{pid}/appointments/{appt['id']}/cancel", headers=h).json() == {"status": "Cancelled"}
    assert client.get("/appointments", params={"patient_id": pid}, headers=auth("admin")).json()[0]["cancel_source"] == "portal"
    assert client.post(f"/portal/{pid}/appointments/{appt['id']}/cancel", headers=h).status_code == 409
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        assert messaging.dispatch_due(db)["sent"] >= 1                                              # bo'shagan vaqt kutuvchiga taklif qilindi
    assert any("/p/o/" in body for _, body in messaging.MockSmsAdapter.SENT)
    other_pid = _patient(client, auth, "Begona", "+998 90 600 00 05")
    other_appt = client.post("/appointments", headers=auth("admin"), json={"patient_id": other_pid, "doctor": DOC, "date": _day(0), "time": "11:00", "type": "Konsultatsiya"}).json()
    assert client.post(f"/portal/{pid}/appointments/{other_appt['id']}/cancel", headers=h).status_code == 404     # boshqaning qabuli


def test_invoices_listed_without_drafts(client, auth, desk=None):
    pid = _patient(client, auth)
    admin = auth("admin")
    svc = client.post("/services", headers=admin, json={"name": "Portal xizmati", "price": 100000, "mxik": "09302001001000000", "package_code": "1", "vat_percent": 12}).json()
    client.post("/invoices", headers=admin, json={"patient_id": pid, "lines": [{"service_id": svc["id"]}]})                    # qoralama
    issued = client.post("/invoices", headers=admin, json={"patient_id": pid, "lines": [{"service_id": svc["id"], "quantity": 2}], "issue": True}).json()
    h = _auth_header(_login(client))
    rows = client.get(f"/portal/{pid}/invoices", headers=h).json()
    assert [(r["number"], r["total"], r["paid"], r["balance"], r["status"]) for r in rows] == [(issued["number"], 200000.0, 0.0, 200000.0, "Issued")]


def _completed_order(client, auth, pid):
    tests = {t["code"]: t for t in client.get("/lab/tests", headers=auth("doctor")).json()}
    order = client.post("/lab/orders", headers=auth("doctor"), json={"patient_id": pid, "doctor": DOC, "test_ids": [tests["GLU"]["id"]]}).json()
    client.put(f"/lab/orders/{order['id']}/results", headers=auth("doctor"), json={"results": [{"item_id": order["items"][0]["id"], "value": 6.5}]})
    return order["id"]


def test_only_doctor_approved_lab_results_visible_and_edit_revokes_approval(client, auth):
    pid = _patient(client, auth, "Natija Bemor")
    oid = _completed_order(client, auth, pid)
    h = _auth_header(_login(client))
    assert client.get(f"/portal/{pid}/lab-results", headers=h).json() == []                       # tasdiqlanmagan: ko'rinmaydi
    assert client.get(f"/portal/{pid}/lab-results/{oid}/pdf", headers=h).status_code == 404
    assert client.post(f"/lab/orders/{oid}/approve", headers=auth("nurse")).status_code == 403    # lab:approve yo'q
    approved = client.post(f"/lab/orders/{oid}/approve", headers=auth("doctor")).json()
    assert approved["approved"] is True and approved["approved_at"]
    rows = client.get(f"/portal/{pid}/lab-results", headers=h).json()
    assert len(rows) == 1 and rows[0]["items"][0]["name"] == "Glyukoza (och qoringa)" and rows[0]["items"][0]["flag"] == "High"
    assert set(rows[0]) == {"id", "date", "doctor", "items"}
    pdf = client.get(f"/portal/{pid}/lab-results/{oid}/pdf", headers=h)
    assert pdf.status_code == 200 and "Natija Bemor" in "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    # tasdiqlangan natija tahrirlanmaydi: faqat tuzatish yozuvi orqali, tasdiq saqlanadi
    item = client.get(f"/lab/orders/{oid}", headers=auth("doctor")).json()["items"][0]["id"]
    assert client.put(f"/lab/orders/{oid}/results", headers=auth("doctor"), json={"results": [{"item_id": item, "value": 5.0}]}).status_code == 409
    assert client.post(f"/lab/orders/{oid}/approve", headers=auth("doctor")).status_code == 409           # qayta tasdiqlanmaydi
    assert client.post(f"/lab/orders/{oid}/approve", headers=auth("doctor"), params={"approved": False}).status_code == 409
    fixed = client.post(f"/lab/orders/{oid}/corrections", headers=auth("doctor"), json={"reason": "Kiritishda xato", "results": [{"item_id": item, "value": 5.0}]}).json()
    assert fixed["approved"] is True and fixed["items"][0]["value"] == 5.0 and fixed["items"][0]["flag"] == "Normal"
    assert client.get(f"/portal/{pid}/lab-results", headers=h).json()[0]["items"][0]["value"] == 5.0


def test_cannot_approve_incomplete_order_and_portal_reads_audited(client, auth):
    pid = _patient(client, auth, "Tugallanmagan")
    tests = {t["code"]: t for t in client.get("/lab/tests", headers=auth("doctor")).json()}
    order = client.post("/lab/orders", headers=auth("doctor"), json={"patient_id": pid, "doctor": DOC, "test_ids": [tests["GLU"]["id"]]}).json()
    assert client.post(f"/lab/orders/{order['id']}/approve", headers=auth("doctor")).status_code == 409
    h = _auth_header(_login(client))
    client.get(f"/portal/{pid}/appointments", headers=h)
    audit = client.get("/security/audit", params={"entity_type": "appointment", "limit": 20}, headers=auth("admin")).json()["items"]
    assert any(e["details"].get("via") == "portal" for e in audit)
