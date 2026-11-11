from datetime import date, timedelta

from tests.test_patients import NEW
from tests.test_schedule import _day, _doctor_id

DOC = "Dr. Behruz Rustamov"  # demo: Du-Ju 09:00-17:00, tanaffus 13:00-14:00


def _patient(client, h, name):
    return client.post("/patients", json={**NEW, "name": name}, headers=h).json()["id"]


def _wait(client, h, pid, **kw):
    return client.post("/waitlist", headers=h, json={"patient_id": pid, "doctor": DOC, **kw})


def test_add_list_fifo_duplicates_and_validation(client, auth):
    h = auth("receptionist")
    p1, p2 = _patient(client, h, "Birinchi Kutuvchi"), _patient(client, h, "Ikkinchi Kutuvchi")
    monday = date.fromisoformat(_day(0))
    friday = (monday + timedelta(days=4)).isoformat()
    a = _wait(client, h, p1, date_from=monday.isoformat(), date_to=friday)
    assert a.status_code == 201 and a.json()["status"] == "Waiting" and a.json()["doctor"] == DOC
    assert _wait(client, h, p1).status_code == 409                                  # bir bemor bir shifokorni ikki marta kutmaydi
    _wait(client, h, p2)                                                            # oraliqsiz: bugundan cheklovsiz
    names = [e["patient_name"] for e in client.get("/waitlist", headers=h).json()]
    assert names == ["Birinchi Kutuvchi", "Ikkinchi Kutuvchi"]                      # eng eski birinchi
    on = client.get("/waitlist", params={"for_date": (monday + timedelta(days=2)).isoformat()}, headers=h).json()    # ikkalasi ham shu sanani xohlaydi
    assert len(on) == 2
    far = (monday + timedelta(days=34)).isoformat()
    assert [e["patient_name"] for e in client.get("/waitlist", params={"for_date": far}, headers=h).json()] == ["Ikkinchi Kutuvchi"]
    assert _wait(client, h, _patient(client, h, "Xato"), date_from="2027-02-02", date_to="2027-01-01").status_code == 422
    assert _wait(client, h, _patient(client, h, "Xato2"), date_from="2027-13-40").status_code == 422
    assert client.post("/waitlist", headers=h, json={"patient_id": p1}).status_code == 422  # shifokorsiz


def test_suggestions_skip_days_off_and_busy_slots(client, auth):
    h = auth("admin")
    pid = _patient(client, h, "Taklif Sinov")
    saturday, monday = _day(5), _day(0)
    # shanba dam olish kuni; dushanba 09:00 band
    entry = _wait(client, h, pid, date_from=saturday, date_to=(date.fromisoformat(saturday) + timedelta(days=3)).isoformat()).json()
    other = _patient(client, h, "Band Qiluvchi")
    client.post("/appointments", headers=h, json={"patient_id": other, "doctor": DOC, "date": (date.fromisoformat(saturday) + timedelta(days=2)).isoformat(),
                                                  "time": "09:00", "type": "Konsultatsiya"})
    sug = client.get(f"/waitlist/{entry['id']}/suggestions", params={"limit": 4}, headers=h).json()
    monday_after = (date.fromisoformat(saturday) + timedelta(days=2)).isoformat()
    assert [s["date"] for s in sug] == [monday_after] * 3 + [(date.fromisoformat(monday_after) + timedelta(days=1)).isoformat()]
    assert [s["time"] for s in sug[:3]] == ["09:30", "09:45", "10:00"]               # 09:00-09:30 band
    assert monday  # (sana yordamchisi ishlatilgan)


def test_book_from_waitlist_marks_booked_and_creates_appointment(client, auth):
    h = auth("receptionist")
    pid = _patient(client, h, "Band Bo'luvchi")
    day = _day(1)
    entry = _wait(client, h, pid, type="Tekshiruv", date_from=day).json()
    booked = client.post(f"/waitlist/{entry['id']}/book", headers=h, json={"date": day, "time": "10:00"})
    assert booked.status_code == 201
    appt = booked.json()
    assert appt["type"] == "Tekshiruv" and appt["duration_min"] == 45 and appt["patient_id"] == pid
    assert client.get("/waitlist", headers=h).json() == []                           # endi Waiting emas
    done = client.get("/waitlist", params={"status": "Booked"}, headers=h).json()
    assert done[0]["appointment_id"] == appt["id"]
    assert client.post(f"/waitlist/{entry['id']}/book", headers=h, json={"date": day, "time": "11:00"}).status_code == 409
    assert client.patch(f"/waitlist/{entry['id']}", headers=h, json={"notes": "x"}).status_code == 409


def test_failed_booking_keeps_entry_waiting(client, auth):
    h = auth("receptionist")
    p1, p2 = _patient(client, h, "Bir"), _patient(client, h, "Ikki")
    day = _day(2)
    client.post("/appointments", headers=h, json={"patient_id": p1, "doctor": DOC, "date": day, "time": "10:00", "type": "Konsultatsiya"})
    entry = _wait(client, h, p2, date_from=day).json()
    clash = client.post(f"/waitlist/{entry['id']}/book", headers=h, json={"date": day, "time": "10:15"})
    off = client.post(f"/waitlist/{entry['id']}/book", headers=h, json={"date": day, "time": "13:00"})
    assert clash.status_code == 409 and off.status_code == 422
    still = client.get("/waitlist", headers=h).json()
    assert [e["id"] for e in still] == [entry["id"]] and still[0]["appointment_id"] is None
    ok = client.post(f"/waitlist/{entry['id']}/book", headers=h, json={"date": day, "time": "10:30"})
    assert ok.status_code == 201


def test_cancel_update_and_permissions(client, auth):
    h = auth("receptionist")
    pid = _patient(client, h, "Bekor Sinov")
    entry = _wait(client, h, pid).json()
    upd = client.patch(f"/waitlist/{entry['id']}", headers=h, json={"notes": "Ertalab", "date_to": _day(4)}).json()
    assert upd["notes"] == "Ertalab" and upd["date_to"] == _day(4)
    assert client.patch(f"/waitlist/{entry['id']}", headers=h, json={"date_to": "2000-01-01"}).status_code == 422
    assert client.patch(f"/waitlist/{entry['id']}", headers=h, json={"status": "Booked"}).status_code == 422
    assert client.patch(f"/waitlist/{entry['id']}", headers=h, json={"status": "Cancelled"}).json()["status"] == "Cancelled"
    assert client.get("/waitlist", headers=h).json() == []
    assert _wait(client, h, pid).status_code == 201                                  # bekor qilingandan keyin qayta qo'shish mumkin
    assert client.get("/waitlist", headers=auth("cashier")).status_code == 200      # appointments:read
    assert client.post("/waitlist", headers=auth("cashier"), json={"patient_id": pid, "doctor": DOC}).status_code == 403
    assert _doctor_id(client, auth("admin"))
