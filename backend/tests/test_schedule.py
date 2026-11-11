from datetime import date, datetime, timedelta

from app.services.periods import CLINIC_TZ
from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"  # demo: Du-Ju 09:00-17:00, tanaffus 13:00-14:00, kabinet 101


def _day(weekday: int, weeks_ahead: int = 30) -> str:
    """Kelajakdagi berilgan hafta kuni (0=dushanba) sanasi."""
    d = date.today() + timedelta(weeks=weeks_ahead)
    return (d + timedelta(days=(weekday - d.weekday()) % 7)).isoformat()


def _doctor_id(client, h, name=DOC):
    return next(s["id"] for s in client.get("/staff", headers=h).json() if s["name"] == name)


def _book(client, h, pid, day, at, **kw):
    return client.post("/appointments", headers=h, json={
        "patient_id": pid, "doctor": DOC, "date": day, "time": at, "type": "Konsultatsiya", **kw})


def _patient(client, h, name="Jadval Sinov"):
    return client.post("/patients", json={**NEW, "name": name}, headers=h).json()["id"]


def test_demo_schedule_and_template_validation(client, auth):
    h = auth("admin")
    sid = _doctor_id(client, h)
    sched = client.get(f"/staff/{sid}/schedule", headers=auth("receptionist")).json()
    assert [d["weekday"] for d in sched["days"]] == [0, 1, 2, 3, 4]
    assert sched["days"][0]["break_start"] == "13:00:00"
    bad = [
        {"weekday": 0, "start_time": "17:00", "end_time": "09:00"},
        {"weekday": 0, "start_time": "09:00", "end_time": "17:00", "break_start": "08:00", "break_end": "09:30"},
        {"weekday": 0, "start_time": "09:00", "end_time": "17:00", "break_start": "13:00"},
        {"weekday": 7, "start_time": "09:00", "end_time": "17:00"},
    ]
    for day in bad:
        assert client.put(f"/staff/{sid}/schedule", json={"days": [day]}, headers=h).status_code == 422, day
    dup = {"weekday": 1, "start_time": "09:00", "end_time": "12:00"}
    assert client.put(f"/staff/{sid}/schedule", json={"days": [dup, dup]}, headers=h).status_code == 422
    assert client.put(f"/staff/{sid}/schedule", json={"days": [dup]}, headers=auth("receptionist")).status_code == 403
    ok = client.put(f"/staff/{sid}/schedule", json={"days": [dup]}, headers=h).json()
    assert [d["weekday"] for d in ok["days"]] == [1]
    nurse = next(s["id"] for s in client.get("/staff", headers=h).json() if s["role"] == "Nurse")
    assert client.get(f"/staff/{nurse}/schedule", headers=h).status_code == 404  # faqat shifokor


def test_booking_must_fit_working_hours(client, auth):
    h = auth("receptionist")
    pid = _patient(client, h)
    monday, saturday = _day(0), _day(5)
    assert _book(client, h, pid, monday, "09:00").status_code == 201
    assert _book(client, h, pid, monday, "16:30").status_code == 201            # 16:30-17:00 sig'adi
    for day, at in ((monday, "08:30"), (monday, "16:45"), (monday, "12:45"), (monday, "13:30"), (saturday, "10:00")):
        res = _book(client, h, pid, day, at)
        assert res.status_code == 422 and "ishlamaydi" in res.json()["detail"], (day, at)
    assert _book(client, h, pid, monday, "14:00").status_code == 201            # tanaffusdan keyin


def test_doctor_without_template_is_unrestricted(client, auth):
    h = auth("admin")
    sid = _doctor_id(client, h)
    client.put(f"/staff/{sid}/schedule", json={"days": []}, headers=h)
    assert _book(client, h, _patient(client, h), _day(6), "03:00").status_code == 201


def test_vacation_blocks_and_reports_affected_then_removal_restores(client, auth):
    h = auth("admin")
    sid = _doctor_id(client, h)
    pid = _patient(client, h)
    monday = _day(0)
    existing = _book(client, h, pid, monday, "10:00").json()
    start = date.fromisoformat(monday)
    vac = client.post(f"/staff/{sid}/schedule/exceptions", headers=h, json={
        "kind": "Vacation", "date_from": monday, "date_to": (start + timedelta(days=4)).isoformat(), "note": "Ta'til"})
    assert vac.status_code == 201 and vac.json()["affected_appointments"] == [existing["id"]]
    assert _book(client, h, pid, (start + timedelta(days=1)).isoformat(), "10:00").status_code == 422
    assert _book(client, h, pid, (start + timedelta(days=7)).isoformat(), "10:00").status_code == 201  # keyingi hafta
    assert client.delete(f"/staff/{sid}/schedule/exceptions/{vac.json()['id']}", headers=h).status_code == 200
    assert _book(client, h, pid, (start + timedelta(days=1)).isoformat(), "10:00").status_code == 201


def test_extra_work_day_overrides_template(client, auth):
    h = auth("admin")
    sid = _doctor_id(client, h)
    pid = _patient(client, h)
    saturday = _day(5)
    assert _book(client, h, pid, saturday, "10:00").status_code == 422
    extra = client.post(f"/staff/{sid}/schedule/exceptions", headers=h, json={
        "kind": "ExtraWork", "date_from": saturday, "start_time": "10:00", "end_time": "14:00",
        "break_start": "12:00", "break_end": "12:30"})
    assert extra.status_code == 201 and extra.json()["affected_appointments"] == []
    assert _book(client, h, pid, saturday, "10:00").status_code == 201
    assert _book(client, h, pid, saturday, "12:00").status_code == 422          # tanaffus
    assert _book(client, h, pid, saturday, "14:00").status_code == 422          # tugagan
    # ExtraWork dam olish istisnosidan ustun
    client.post(f"/staff/{sid}/schedule/exceptions", headers=h, json={"kind": "DayOff", "date_from": saturday})
    assert _book(client, h, pid, saturday, "13:00").status_code == 201


def test_exception_validation(client, auth):
    h = auth("admin")
    sid = _doctor_id(client, h)
    url = f"/staff/{sid}/schedule/exceptions"
    d = _day(5)
    assert client.post(url, headers=h, json={"kind": "ExtraWork", "date_from": d}).status_code == 422
    assert client.post(url, headers=h, json={"kind": "Vacation", "date_from": d, "start_time": "10:00",
                                             "end_time": "12:00"}).status_code == 422
    assert client.post(url, headers=h, json={"kind": "Sick", "date_from": d,
                                            "date_to": (date.fromisoformat(d) - timedelta(days=1)).isoformat()}).status_code == 422
    assert client.post(url, headers=h, json={"kind": "ExtraWork", "date_from": d, "date_to": _day(6),
                                             "start_time": "10:00", "end_time": "12:00"}).status_code == 422
    assert client.post(url, headers=h, json={"kind": "Sick", "date_from": d}).status_code == 201


def test_free_slots(client, auth):
    h = auth("receptionist")
    sid = _doctor_id(client, h)
    monday = _day(0)
    res = client.get(f"/staff/{sid}/slots", params={"date": monday, "step_min": 30}, headers=h).json()
    times = [s["time"] for s in res["slots"]]
    assert res["duration_min"] == 30 and res["room_id"]
    assert times[:3] == ["09:00", "09:30", "10:00"] and "13:00" not in times and "13:30" not in times
    assert times[-1] == "16:30" and len(times) == 14
    pid = _patient(client, h)
    _book(client, h, pid, monday, "10:00")
    after = [s["time"] for s in client.get(f"/staff/{sid}/slots", params={"date": monday, "step_min": 30}, headers=h).json()["slots"]]
    assert "10:00" not in after and len(after) == 13
    # uzoqroq tur: 90 daqiqa Jarrohlik 11:30-13:00 sig'adi (tanaffus boshida tugaydi), 12:00 sig'maydi
    long_ = client.get(f"/staff/{sid}/slots", params={"date": monday, "type": "Jarrohlik", "step_min": 30}, headers=h).json()
    long_times = [s["time"] for s in long_["slots"]]
    assert long_["duration_min"] == 90 and "11:30" in long_times and "12:00" not in long_times
    assert "10:00" not in long_times and "14:00" in long_times  # 10:00-11:30 band qabul bilan kesishadi
    # dam olish kunida bo'sh vaqt yo'q
    assert client.get(f"/staff/{sid}/slots", params={"date": _day(6)}, headers=h).json()["slots"] == []


def test_slots_exclude_busy_room_of_other_doctor(client, auth):
    h = auth("admin")
    sid = _doctor_id(client, h)
    karimova = _doctor_id(client, h, "Dr. Zulfiya Karimova")
    pid = _patient(client, h)
    rooms = {r["name"]: r["id"] for r in client.get("/rooms", headers=h).json()}
    monday = _day(0)
    client.post("/appointments", headers=h, json={"patient_id": pid, "doctor_id": karimova, "date": monday,
                                                  "time": "11:00", "type": "Konsultatsiya", "room_id": rooms["101"]})
    times = [s["time"] for s in client.get(f"/staff/{sid}/slots", params={"date": monday, "step_min": 30}, headers=h).json()["slots"]]
    assert "11:00" not in times and "10:30" in times and "11:30" in times


def test_slots_today_have_no_past_times(client, auth):
    h = auth("admin")
    free = client.post("/staff", headers=h, json={"name": "Dr. Bugun", "role": "Doctor", "department": "Terapiya",
                                                  "phone": "+998 90 000 00 02", "email": "bugun@clinic.uz"}).json()
    today = datetime.now(CLINIC_TZ).date().isoformat()
    slots = client.get(f"/staff/{free['id']}/slots", params={"date": today}, headers=h).json()["slots"]
    now = datetime.now(CLINIC_TZ).strftime("%H:%M")
    assert all(s["time"] >= now for s in slots)
