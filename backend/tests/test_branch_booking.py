"""Onlayn yozilish va bemor portalida filial tanlash (v1.9.18); kutish ro'yxati taklifi faqat o'sha filialga."""
import re
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Appointment, Message
from app.services import messaging
from tests.test_patients import NEW
from tests.test_portal import _auth_header, _login

DOC = "Dr. Behruz Rustamov"       # asosiy filialda Du-Ju 09:00-17:00


def _on(h, bid):
    return {**h, "X-Branch-Id": bid}


def _monday():
    d = date.today() + timedelta(days=14)
    return (d + timedelta(days=(0 - d.weekday()) % 7)).isoformat()


@pytest.fixture(autouse=True)
def _clear():
    messaging.MockSmsAdapter.SENT.clear()


@pytest.fixture
def world(client, auth):
    """Ikkinchi filial: shifokor dushanba 18:00-20:00 da ishlaydi."""
    admin = auth("admin")
    b = client.post("/branches", json={"name": "Onlayn filial", "address": "Chilonzor 7", "phone": "+998 71 111 11 11"}, headers=admin).json()["id"]
    doc = next(s for s in client.get("/staff", headers=admin).json() if s["name"] == DOC)
    client.put(f"/staff/{doc['id']}/branches", json={"branch_ids": [b]}, headers=admin)
    client.put(f"/staff/{doc['id']}/schedule", headers=_on(admin, b), json={"days": [
        {"weekday": 0, "start_time": "18:00:00", "end_time": "20:00:00", "break_start": None, "break_end": None}]})
    return admin, b, doc["id"]


def _otp_token(client, phone, purpose="booking"):
    client.post("/public/otp/request", json={"phone": phone, "purpose": purpose})
    code = re.search(r"\b(\d{6})\b", messaging.MockSmsAdapter.SENT[-1][1]).group(1)
    return client.post("/public/otp/verify", json={"phone": phone, "purpose": purpose, "code": code}).json()["token"]


def test_public_lists_active_branches_doctors_and_slots_per_branch(client, world):
    admin, b, doc = world
    branches = client.get("/public/booking/branches").json()
    assert branches[0]["is_default"] is True and [x["name"] for x in branches][1] == "Onlayn filial" and branches[1]["address"] == "Chilonzor 7"
    assert DOC in [d["name"] for d in client.get("/public/booking/doctors").json()]                                  # sarlavhasiz: asosiy filial
    assert [d["name"] for d in client.get("/public/booking/doctors", params={"branch_id": b}).json()] == [DOC]       # ikkinchi filialda faqat shu shifokor
    mon = _monday()
    a = client.get("/public/booking/slots", params={"doctor_id": doc, "date": mon, "type": "Konsultatsiya"}).json()["slots"]
    s = client.get("/public/booking/slots", params={"doctor_id": doc, "date": mon, "type": "Konsultatsiya", "branch_id": b}).json()["slots"]
    assert a[0] == "09:00" and all(t < "17:00" for t in a) and s[0] == "18:00" and all(t >= "18:00" for t in s)
    assert client.get("/public/booking/doctors", params={"branch_id": "garbage"}).status_code == 422
    client.put(f"/branches/{b}", json={"is_active": False}, headers=admin)
    assert len(client.get("/public/booking/branches").json()) == 1                                                   # faolsiz filial ko'rinmaydi
    assert client.get("/public/booking/doctors", params={"branch_id": b}).status_code == 422


def test_online_booking_creates_appointment_in_chosen_branch(client, auth, world):
    admin, b, doc = world
    mon = _monday()
    token = _otp_token(client, "+998 90 710 00 01")
    body = {"token": token, "name": "Filial Onlayn", "doctor_id": doc, "type": "Konsultatsiya", "date": mon, "time": "18:30", "branch_id": b}
    wrong_time = client.post("/public/booking", json={**body, "time": "10:00"})                                      # ikkinchi filialda 10:00 ish vaqti emas
    assert wrong_time.status_code == 422
    ok = client.post("/public/booking", json=body)
    assert ok.status_code == 201, ok.text
    with SessionLocal() as db:
        from app.models import Patient
        patient = db.scalar(select(Patient).where(Patient.full_name == "Filial Onlayn"))
        appt = db.scalar(select(Appointment).where(Appointment.patient_id == patient.id))
        assert str(appt.branch_id) == b and str(patient.branch_id) == b                                             # qabul va yangi bemor tanlangan filialda
    assert len(client.get("/appointments", params={"date": mon}, headers=_on(admin, b)).json()) == 1
    assert [a for a in client.get("/appointments", params={"date": mon}, headers=admin).json() if a["patient_name"] == "Filial Onlayn"] == []
    assert client.post("/public/booking", json={**body, "token": _otp_token(client, "+998 90 710 00 02"), "name": "Boshqa Filial",
                                                "branch_id": "00000000-0000-0000-0000-000000000000"}).status_code == 422
    third = client.post("/branches", json={"name": "Shifokorsiz filial"}, headers=admin).json()["id"]
    res = client.post("/public/booking", json={**body, "token": _otp_token(client, "+998 90 710 00 03"), "name": "Uchinchi Filial", "branch_id": third})
    assert res.status_code == 422 and "bu filialda ishlamaydi" in res.json()["detail"]
    default = client.post("/public/booking", json={"token": _otp_token(client, "+998 90 710 00 04"), "name": "Asosiy Filial", "doctor_id": doc,
                                                   "type": "Konsultatsiya", "date": mon, "time": "10:00"})        # branch_id yo'q: asosiy filial
    assert default.status_code == 201 and len([a for a in client.get("/appointments", params={"date": mon}, headers=admin).json()
                                               if a["patient_name"] == "Asosiy Filial"]) == 1


def test_portal_books_in_chosen_branch_and_shows_branch_names(client, auth, world):
    admin, b, doc = world
    phone = "+998 90 720 00 01"
    pid = client.post("/patients", json={**NEW, "name": "Portal Filial", "phone": phone}, headers=admin).json()["id"]
    h = _auth_header(_login(client, phone))
    mon = _monday()
    body = {"branch_id": b, "doctor_id": doc, "type": "Konsultatsiya", "date": mon, "time": "19:00"}
    assert client.post(f"/portal/{pid}/appointments", json=body).status_code == 401                                   # seanssiz
    assert client.post(f"/portal/{pid}/appointments", json={**body, "time": "10:00"}, headers=h).status_code == 422
    res = client.post(f"/portal/{pid}/appointments", json=body, headers=h)
    assert res.status_code == 201 and res.json()["branch"] == "Onlayn filial" and res.json()["time"] == "19:00"
    main = client.post(f"/portal/{pid}/appointments", json={"doctor_id": doc, "type": "Konsultatsiya", "date": mon, "time": "10:00"}, headers=h)
    assert main.status_code == 201 and main.json()["branch"] != "Onlayn filial"                                      # filial tanlanmasa asosiy
    listed = client.get(f"/portal/{pid}/appointments", headers=h).json()
    assert {(a["time"], a["branch"]) for a in listed if a["status"] == "Scheduled"} == {("19:00", "Onlayn filial"), ("10:00", main.json()["branch"])}
    other = client.post("/patients", json={**NEW, "name": "Begona Bemor", "phone": "+998 90 720 00 02"}, headers=admin).json()["id"]
    assert client.post(f"/portal/{other}/appointments", json=body, headers=h).status_code == 404                     # boshqa telefon bemoriga yozib bo'lmaydi
    for t in ("18:00", "18:30"):                                                                                      # faol qabullar limiti: 3 ta
        client.post(f"/portal/{pid}/appointments", json={**body, "time": t}, headers=h)
    assert client.post(f"/portal/{pid}/appointments", json={**body, "time": "19:30"}, headers=h).status_code == 409


def test_waitlist_offer_goes_only_to_waiters_of_the_same_branch(client, auth, world):
    admin, b, doc = world
    mon = _monday()
    other = _on(admin, b)
    def patient(name, phone, h):
        pid = client.post("/patients", json={**NEW, "name": name, "phone": phone}, headers=h).json()["id"]
        client.put(f"/patients/{pid}/consents", headers=admin, json={"channel": "SMS", "granted": True})
        return pid
    booker = patient("Bekor Qiluvchi", "+998 90 730 00 01", other)
    appt = client.post("/appointments", headers=other, json={"patient_id": booker, "doctor": DOC, "date": mon, "time": "18:00", "type": "Konsultatsiya"})
    assert appt.status_code == 201
    in_main = patient("Asosiy Kutuvchi", "+998 90 730 00 02", admin)
    client.post("/waitlist", headers=admin, json={"patient_id": in_main, "doctor": DOC, "date_from": mon, "date_to": mon})        # asosiy filial navbati
    client.patch(f"/appointments/{appt.json()['id']}/status", params={"status": "Cancelled"}, headers=other)
    with SessionLocal() as db:
        messaging.dispatch_due(db)
        assert db.scalars(select(Message).where(Message.kind == "waitlist_offer")).all() == []                              # boshqa filial navbatiga taklif ketmadi
    in_b = patient("Filial Kutuvchi", "+998 90 730 00 03", other)
    client.post("/waitlist", headers=other, json={"patient_id": in_b, "doctor": DOC, "date_from": mon, "date_to": mon})
    appt2 = client.post("/appointments", headers=other, json={"patient_id": booker, "doctor": DOC, "date": mon, "time": "19:00", "type": "Konsultatsiya"})
    client.patch(f"/appointments/{appt2.json()['id']}/status", params={"status": "Cancelled"}, headers=other)
    with SessionLocal() as db:
        messaging.dispatch_due(db)
    assert [to for to, _ in messaging.MockSmsAdapter.SENT if "bo'sh vaqt" in _] == ["+998907300003"]                         # faqat shu filial kutuvchisiga
