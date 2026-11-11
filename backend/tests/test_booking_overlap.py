from concurrent.futures import ThreadPoolExecutor

from tests.test_patients import NEW

DOC, DOC2 = "Dr. Behruz Rustamov", "Dr. Zulfiya Karimova"


def _patient(client, h, name="Bemor"):
    return client.post("/patients", json={**NEW, "name": f"{name} Sinov"}, headers=h).json()["id"]


def _book(client, h, pid, **kw):
    body = {"patient_id": pid, "doctor": DOC, "date": "2027-04-01", "time": "10:00", "type": "Konsultatsiya", **kw}
    return client.post("/appointments", json=body, headers=h)


def test_doctor_cannot_be_double_booked_but_back_to_back_is_ok(client, auth):
    h = auth("receptionist")
    p1, p2 = _patient(client, h, "Bir"), _patient(client, h, "Ikki")
    assert _book(client, h, p1).status_code == 201                                  # 10:00-10:30
    clash = _book(client, h, p2, time="10:15")
    assert clash.status_code == 409 and "Shifokor" in clash.json()["detail"]
    assert _book(client, h, p2, time="09:45").status_code == 409                    # 09:45-10:15 kesishadi
    assert _book(client, h, p2, time="10:30").status_code == 201                    # ketma-ket: ruxsat
    assert _book(client, h, p2, time="09:30").status_code == 201                    # 09:30-10:00: ruxsat


def test_room_cannot_be_double_booked_even_with_different_doctors(client, auth):
    h = auth("admin")
    p1, p2 = _patient(client, h, "Bir"), _patient(client, h, "Ikki")
    rooms = {r["name"]: r["id"] for r in client.get("/rooms", headers=h).json()}
    assert _book(client, h, p1, room_id=rooms["101"]).status_code == 201
    clash = _book(client, h, p2, doctor=DOC2, room_id=rooms["101"])
    assert clash.status_code == 409 and "Kabinet" in clash.json()["detail"]
    assert _book(client, h, p2, doctor=DOC2).status_code == 201                    # o'zining kabineti (102)


def test_default_room_is_used_and_returned(client, auth):
    h = auth("admin")
    appt = _book(client, h, _patient(client, h)).json()
    assert appt["room"] == "101" and appt["room_id"]


def test_cancelled_and_no_show_free_the_slot_and_reactivation_conflicts(client, auth):
    h = auth("admin")
    p1, p2 = _patient(client, h, "Bir"), _patient(client, h, "Ikki")
    first = _book(client, h, p1).json()
    assert client.patch(f"/appointments/{first['id']}/status", params={"status": "Cancelled"}, headers=h).status_code == 200
    second = _book(client, h, p2)
    assert second.status_code == 201                                               # bekor qilingan vaqt bo'sh
    again = client.patch(f"/appointments/{first['id']}/status", params={"status": "Scheduled"}, headers=h)
    assert again.status_code == 409                                                # qayta faollashtirish to'qnashadi


def test_reschedule_checks_overlap_and_status(client, auth):
    h = auth("admin")
    p1, p2 = _patient(client, h, "Bir"), _patient(client, h, "Ikki")
    a = _book(client, h, p1).json()
    b = _book(client, h, p2, time="11:00").json()
    assert client.patch(f"/appointments/{b['id']}", json={"time": "10:10"}, headers=h).status_code == 409
    moved = client.patch(f"/appointments/{b['id']}", json={"time": "10:30", "type": "Jarrohlik"}, headers=h)
    assert moved.status_code == 200 and (moved.json()["time"], moved.json()["end_time"]) == ("10:30", "12:00")
    shifted = client.patch(f"/appointments/{a['id']}", json={"date": "2027-04-05"}, headers=h).json()
    assert shifted["date"] == "2027-04-05" and shifted["time"] == "10:00"
    # shifokor almashganda kabinet ham almashadi
    to_doc2 = client.patch(f"/appointments/{a['id']}", json={"doctor": DOC2}, headers=h).json()
    assert to_doc2["room"] == "102"
    client.patch(f"/appointments/{b['id']}/status", params={"status": "Completed"}, headers=h)
    assert client.patch(f"/appointments/{b['id']}", json={"time": "14:00"}, headers=h).status_code == 409


def test_concurrent_bookings_only_one_wins(client, auth):
    h = auth("admin")
    pids = [_patient(client, h, f"P{i}") for i in range(6)]
    with ThreadPoolExecutor(6) as pool:
        codes = list(pool.map(lambda pid: _book(client, h, pid, date="2027-05-03").status_code, pids))
    assert sorted(codes) == [201] + [409] * 5


def test_rooms_crud_permissions_and_deactivation(client, auth):
    admin, rec = auth("admin"), auth("receptionist")
    assert client.post("/rooms", json={"name": "201"}, headers=rec).status_code == 403
    room = client.post("/rooms", json={"name": "201", "description": "Laboratoriya"}, headers=admin)
    assert room.status_code == 201
    assert client.post("/rooms", json={"name": " 201 "}, headers=admin).status_code == 409  # registrsiz unikal, bo'sh joylar kesiladi
    assert client.post("/rooms", json={"name": "A-1"}, headers=admin).status_code == 201
    assert client.post("/rooms", json={"name": "a-1"}, headers=admin).status_code == 409
    rid = room.json()["id"]
    pid = _patient(client, admin)
    assert _book(client, admin, pid, room_id=rid).status_code == 201
    res = client.delete(f"/rooms/{rid}", headers=admin)                           # ishlatilgan: faolsizlantiriladi
    assert "faolsizlantirildi" in res.json()["message"]
    assert rid not in [r["id"] for r in client.get("/rooms", headers=admin).json()]
    assert _book(client, admin, pid, time="12:00", room_id=rid).status_code == 422  # faol bo'lmagan kabinet
    # shifokorning standart kabineti
    doc = next(s for s in client.get("/staff", headers=admin).json() if s["name"] == DOC)
    new_room = client.post("/rooms", json={"name": "301"}, headers=admin).json()
    upd = client.put(f"/staff/{doc['id']}", json={"default_room_id": new_room["id"]}, headers=admin).json()
    assert upd["default_room_id"] == new_room["id"]
    assert client.put(f"/staff/{doc['id']}", json={"default_room_id": None}, headers=admin).json()["default_room_id"] is None
