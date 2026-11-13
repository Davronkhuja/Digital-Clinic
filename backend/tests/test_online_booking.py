import re
from datetime import date, timedelta

import pytest

from app.services import messaging
from tests.test_patients import NEW


def _day(weekday: int) -> str:
    """Kelgusi 2-3 hafta ichidagi hafta kuni (onlayn yozilish 60 kun bilan cheklangan)."""
    d = date.today() + timedelta(days=14)
    return (d + timedelta(days=(weekday - d.weekday()) % 7)).isoformat()

DOC = "Dr. Behruz Rustamov"   # Du-Ju 09:00-17:00, tanaffus 13:00-14:00


@pytest.fixture(autouse=True)
def _clear():
    messaging.MockSmsAdapter.SENT.clear()


def _otp(client, phone="+998 90 321 00 01", purpose="booking", **kw):
    res = client.post("/public/otp/request", json={"phone": phone, "purpose": purpose, **kw})
    assert res.status_code == 200, res.text
    return re.search(r"\b(\d{6})\b", messaging.MockSmsAdapter.SENT[-1][1]).group(1)


def _token(client, phone="+998 90 321 00 01", purpose="booking"):
    code = _otp(client, phone, purpose)
    res = client.post("/public/otp/verify", json={"phone": phone, "purpose": purpose, "code": code})
    assert res.status_code == 200, res.text
    return res.json()["token"]


def _doctor_id(client):
    return next(d["id"] for d in client.get("/public/booking/doctors").json() if d["name"] == DOC)


def _book(client, token, time="10:00", day=None, name="Onlayn Bemor", **kw):
    return client.post("/public/booking", json={"token": token, "name": name, "doctor_id": _doctor_id(client), "type": "Konsultatsiya",
                                                "date": day or _day(0), "time": time, **kw})


def test_otp_roundtrip_hashing_attempts_and_purpose(client, auth):
    code = _otp(client)
    assert messaging.MockSmsAdapter.SENT[-1][0] == "+998903210001"                   # tranzaksion: rozilik talab qilinmaydi
    logged = client.get("/messages", params={"kind": "otp"}, headers=auth("admin")).json()[0]
    assert code not in logged["body"] and logged["to_address"].startswith("***")
    wrong = "000000" if code != "000000" else "111111"
    assert client.post("/public/otp/verify", json={"phone": "+998 90 321 00 01", "code": wrong}).status_code == 400
    ok = client.post("/public/otp/verify", json={"phone": "90 321 00 01", "code": code})                # telefon formati farqi muhim emas
    assert ok.status_code == 200 and "." in ok.json()["token"]
    assert client.post("/public/otp/verify", json={"phone": "+998 90 321 00 01", "code": code}).status_code == 400   # bir marta ishlatiladi
    # noto'g'ri urinishlar chegarasi
    code2 = _otp(client, "+998 90 321 00 02")
    for _ in range(5):
        client.post("/public/otp/verify", json={"phone": "+998 90 321 00 02", "code": "000000" if code2 != "000000" else "999999"})
    assert client.post("/public/otp/verify", json={"phone": "+998 90 321 00 02", "code": code2}).status_code == 429    # 5 urinishdan keyin to'g'ri kod ham bekor, telefon bloklangan
    # token boshqa maqsadga yaroqsiz
    portal = _token(client, "+998 90 321 00 03", "portal")
    assert _book(client, portal).status_code == 401
    assert _book(client, "garbage").status_code == 401


def test_otp_rate_limits_honeypot_and_validation(client):
    for _ in range(3):
        assert client.post("/public/otp/request", json={"phone": "+998 90 321 00 04"}).status_code == 200
    limited = client.post("/public/otp/request", json={"phone": "+998 90 321 00 04"})
    assert limited.status_code == 429
    assert client.post("/public/otp/request", json={"phone": "+998 90 321 00 05", "website": "http://spam"}).status_code == 422   # honeypot
    assert client.post("/public/otp/request", json={"phone": "123"}).status_code == 422
    assert client.post("/public/otp/request", json={"phone": "+998 90 321 00 06", "purpose": "other"}).status_code == 422
    assert len(messaging.MockSmsAdapter.SENT) == 3                                  # cheklangan so'rov SMS yubormaydi


def test_ip_rate_limit_on_otp_requests(client):
    for i in range(10):
        assert client.post("/public/otp/request", json={"phone": f"+998 90 400 00 {i:02d}"}).status_code == 200
    assert client.post("/public/otp/request", json={"phone": "+998 90 400 00 99"}).status_code == 429


def test_public_catalog_and_slots(client):
    types = {t["name"]: t["duration_min"] for t in client.get("/public/booking/types").json()}
    assert types["Konsultatsiya"] == 30
    doctors = client.get("/public/booking/doctors").json()
    assert DOC in [d["name"] for d in doctors] and all(set(d) == {"id", "name", "department"} for d in doctors)
    slots = client.get("/public/booking/slots", params={"doctor_id": _doctor_id(client), "date": _day(0), "type": "Konsultatsiya"}).json()
    assert slots["duration_min"] == 30 and slots["slots"][0] == "09:00" and "13:00" not in slots["slots"] and slots["slots"][-1] == "16:30"
    far = (date.today() + timedelta(days=61)).isoformat()
    assert client.get("/public/booking/slots", params={"doctor_id": _doctor_id(client), "date": far, "type": "Konsultatsiya"}).status_code == 422
    past = (date.today() - timedelta(days=1)).isoformat()
    assert client.get("/public/booking/slots", params={"doctor_id": _doctor_id(client), "date": past, "type": "Konsultatsiya"}).status_code == 422
    assert client.get("/public/booking/slots", params={"doctor_id": "00000000-0000-0000-0000-000000000000", "date": _day(0), "type": "x"}).status_code == 404


def test_online_booking_creates_patient_with_source_consent_and_confirmation(client, auth):
    token = _token(client)
    res = _book(client, token, language="ru", consent_sms=True, birth_date="1992-04-05")
    assert res.status_code == 201, res.text
    out = res.json()
    assert out["time"] == "10:00" and out["doctor"] == DOC and "/p/a/" in out["manage_link"]
    patients = client.get("/patients", params={"search": "Onlayn Bemor"}, headers=auth("admin")).json()
    assert len(patients) == 1
    p = patients[0]
    assert p["source"] == "onlayn" and p["phone"] == "+998903210001" and p["gender"] == "other" and p["birth_date"] == "1992-04-05"
    prefs = client.get(f"/patients/{p['id']}/contact-preferences", headers=auth("admin")).json()
    sms = next(c for c in prefs["consents"] if c["channel"] == "SMS")
    assert prefs["language"] == "ru" and sms["status"] == "Granted" and sms["source"] == "online"
    appt = client.get("/appointments", params={"patient_id": p["id"]}, headers=auth("admin")).json()[0]
    assert appt["time"] == "10:00" and appt["status"] == "Scheduled"
    # tasdiqlash xabari (rus tilida, havola bilan) va havola ishlaydi
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        messaging.dispatch_due(db)
    to, body = messaging.MockSmsAdapter.SENT[-1]
    assert to == "+998903210001" and "записаны" in body and "/p/a/" in body
    token_link = out["manage_link"].split("/p/a/")[1]
    assert client.get(f"/public/appointments/{token_link}").json()["time"] == "10:00"
    audit = client.get("/security/audit", params={"entity_type": "appointment", "limit": 10}, headers=auth("admin")).json()["items"]
    assert any(e["details"].get("via") == "online" for e in audit)


def test_no_sms_consent_means_no_confirmation_message(client, auth):
    token = _token(client, "+998 90 321 00 07")
    assert _book(client, token, name="Rozilik Bermagan", consent_sms=False).status_code == 201
    messaging.MockSmsAdapter.SENT.clear()
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        messaging.dispatch_due(db)
    assert messaging.MockSmsAdapter.SENT == []


def test_existing_patient_reused_no_duplicate_even_cyrillic_variant(client, auth):
    admin = auth("admin")
    existing = client.post("/patients", json={**NEW, "name": "Абдуллаев Ўктам", "phone": "+998 90 321 00 08", "source": "reklama"}, headers=admin).json()
    token = _token(client, "+998 90 321 00 08")
    assert _book(client, token, name="Abdullayev O'ktam").status_code == 201                  # lotin yozuv: bir xil bemor
    all_patients = client.get("/patients", params={"search": "Abdullayev"}, headers=admin).json()
    assert len(all_patients) == 1 and all_patients[0]["id"] == existing["id"] and all_patients[0]["source"] == "reklama"
    assert client.get("/appointments", params={"patient_id": existing["id"]}, headers=admin).json()[0]["time"] == "10:00"
    # shu telefon, boshqa ism: oila a'zosi sifatida yangi bemor
    assert _book(client, token, time="11:00", name="Boshqa Ism").status_code == 201
    assert len(client.get("/patients", params={"search": "Boshqa Ism"}, headers=admin).json()) == 1
    groups = client.get("/patients/duplicates", headers=admin).json()
    assert groups == []                                                                           # onlayn dublikat hosil qilmadi


def test_booking_rules_conflicts_hours_limits_and_validation(client, auth):
    token = _token(client, "+998 90 321 00 09")
    assert _book(client, token, time="10:00", name="Birinchi").status_code == 201
    taken = _book(client, _token(client, "+998 90 321 00 10"), time="10:15", name="Band")
    assert taken.status_code == 409                                                             # shifokor band
    for bad_time in ("08:00", "13:00", "17:00"):
        assert _book(client, _token(client, f"+998 90 321 01 {bad_time[:2]}"), time=bad_time, name="Soat").status_code == 422   # ish vaqtidan tashqari
    assert _book(client, token, time="11:00", name="Birinchi").status_code == 201
    assert _book(client, token, time="11:30", name="Birinchi").status_code == 201
    limit = _book(client, token, time="12:00", name="Birinchi")
    assert limit.status_code == 409 and "limit" in limit.json()["detail"]                       # bir telefonda 3 faol qabul
    t2 = _token(client, "+998 90 321 00 11")
    far = (date.today() + timedelta(days=90)).isoformat()
    assert _book(client, t2, name="Uzoq", day=far).status_code == 422
    assert client.post("/public/booking", json={"token": t2, "name": "X", "doctor_id": _doctor_id(client), "type": "Konsultatsiya", "date": _day(0), "time": "14:00"}).status_code == 422   # ism qisqa
    assert client.post("/public/booking", json={"token": t2, "name": "Noma'lum Xizmat", "doctor_id": _doctor_id(client), "type": "Yo'q xizmat", "date": _day(0), "time": "14:00"}).status_code == 422
    assert client.post("/public/booking", json={"token": t2, "name": "Honeypot Bot", "doctor_id": _doctor_id(client), "type": "Konsultatsiya", "date": _day(0), "time": "14:00", "website": "x"}).status_code == 422


def test_booking_ip_rate_limit(client):
    ok = 0
    for i in range(6):
        res = _book(client, _token(client, f"+998 90 500 00 {i:02d}"), time=f"{9 + i:02d}:00" if i < 4 else f"{14 + i - 4:02d}:00", name=f"Tezlik {i}")
        ok += res.status_code == 201
        if i == 5:
            assert res.status_code == 429
    assert ok == 5
