from datetime import UTC

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Appointment
from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"


def _book(client, h, patient_id, **kw):
    body = {"patient_id": patient_id, "doctor": DOC, "date": "2027-03-01", "time": "10:00", "type": "Konsultatsiya", **kw}
    return client.post("/appointments", json=body, headers=h)


def _patient(client, h):
    return client.post("/patients", json=NEW, headers=h).json()["id"]


def test_duration_from_type_then_doctor_default_then_override(client, auth):
    h = auth("admin")
    pid = _patient(client, h)
    a = _book(client, h, pid).json()
    assert (a["time"], a["end_time"], a["duration_min"]) == ("10:00", "10:30", 30)
    assert _book(client, h, pid, time="11:00", type="Jarrohlik").json()["duration_min"] == 90
    assert _book(client, h, pid, time="15:00", duration_min=15).json()["end_time"] == "15:15"

    doc = next(s for s in client.get("/staff", headers=h).json() if s["name"] == DOC)
    assert client.put(f"/staff/{doc['id']}", json={"slot_minutes": 20}, headers=h).json()["slot_minutes"] == 20
    unknown = _book(client, h, pid, time="16:00", type="Noma'lum tur").json()  # tur ro'yxatda yo'q -> shifokor standarti
    assert unknown["duration_min"] == 20


def test_times_stored_as_utc_and_shown_in_tashkent(client, auth):
    h = auth("admin")
    created = _book(client, h, _patient(client, h)).json()
    with SessionLocal() as db:
        appt = db.scalar(select(Appointment).where(Appointment.id == created["id"]))
        assert appt.starts_at.tzinfo is not None
        assert appt.starts_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M") == "2027-03-01 05:00"  # UTC+5
    assert created["starts_at"].startswith("2027-03-01T05:00:00")


def test_date_filter_uses_clinic_day_not_utc_day(client, auth):
    h = auth("admin")
    pid = _patient(client, h)
    free = client.post("/staff", headers=h, json={"name": "Dr. Jadvalsiz", "role": "Doctor", "department": "Terapiya",
                                                  "phone": "+998 90 000 00 01", "email": "jadvalsiz@clinic.uz"}).json()
    _book(client, h, pid, doctor_id=free["id"], doctor=None, date="2027-03-02", time="00:30")  # UTC: 1-mart 19:30
    on_2nd = client.get("/appointments", params={"date": "2027-03-02"}, headers=h).json()
    on_1st = client.get("/appointments", params={"date": "2027-03-01"}, headers=h).json()
    assert [a["time"] for a in on_2nd] == ["00:30"] and on_1st == []


def test_invalid_date_time_422(client, auth):
    h = auth("admin")
    pid = _patient(client, h)
    assert _book(client, h, pid, date="2027-13-45").status_code == 422
    assert _book(client, h, pid, time="25:99").status_code == 422


def test_appointment_types_crud_and_permissions(client, auth):
    admin, rec = auth("admin"), auth("receptionist")
    types = {t["name"]: t for t in client.get("/appointment-types", headers=rec).json()}
    assert types["Jarrohlik"]["duration_min"] == 90
    assert client.post("/appointment-types", json={"name": "Yangi", "duration_min": 40}, headers=rec).status_code == 403
    new = client.post("/appointment-types", json={"name": "Yangi tur", "duration_min": 40}, headers=admin)
    assert new.status_code == 201
    assert client.post("/appointment-types", json={"name": "yangi tur"}, headers=admin).status_code == 409
    assert client.put(f"/appointment-types/{new.json()['id']}", json={"duration_min": 4}, headers=admin).status_code == 422
    upd = client.put(f"/appointment-types/{new.json()['id']}", json={"duration_min": 50}, headers=admin)
    assert upd.json()["duration_min"] == 50

    pid = _patient(client, admin)
    assert _book(client, admin, pid, type="Yangi tur").json()["duration_min"] == 50
    res = client.delete(f"/appointment-types/{new.json()['id']}", headers=admin)  # ishlatilgan: faolsizlantiriladi
    assert "faolsizlantirildi" in res.json()["message"]
    assert "Yangi tur" not in [t["name"] for t in client.get("/appointment-types", headers=admin).json()]
