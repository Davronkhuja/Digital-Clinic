from datetime import date, timedelta

from tests.test_patients import NEW
from tests.test_schedule import _day, _doctor_id

DOC = "Dr. Behruz Rustamov"  # demo: Du-Ju 09:00-17:00, tanaffus 13:00-14:00, 101-kabinet


def _senior(client, auth):
    """Katta registrator hisobi (admin yaratadi)."""
    admin = auth("admin")
    staff = client.post("/users", headers=admin, json={
        "name": "Katta Registrator", "email": "senior@clinic.uz", "password": "password123", "role": "senior_receptionist",
        "department": "Qabul", "phone": "+998 90 000 11 22"})
    assert staff.status_code in (200, 201), staff.text
    return {"Authorization": "Bearer " + client.post("/auth/login", json={"email": "senior@clinic.uz",
                                                                          "password": "password123"}).json()["access_token"]}


def _patient(client, auth, name="Override Bemor"):
    return client.post("/patients", json={**NEW, "name": name}, headers=auth("admin")).json()["id"]


def _book(client, h, pid, day, at, **kw):
    return client.post("/appointments", headers=h, json={"patient_id": pid, "doctor": DOC, "date": day, "time": at,
                                                        "type": "Konsultatsiya", **kw})


def test_permission_holders_and_role_seed(client, auth):
    roles = {r["code"]: r for r in client.get("/roles", headers=auth("admin")).json()}
    assert "appointments:override" in roles["admin"]["permissions"]
    senior = roles["senior_receptionist"]["permissions"]
    assert "appointments:override" in senior and "appointments:write" in senior and "patients:merge" in senior
    for code in ("receptionist", "doctor", "nurse", "cashier"):
        assert "appointments:override" not in roles[code]["permissions"]


def test_outside_hours_needs_reason_and_permission(client, auth):
    pid = _patient(client, auth)
    monday, saturday = _day(0), _day(5)
    rec, admin = auth("receptionist"), auth("admin")
    plain = _book(client, rec, pid, saturday, "10:00")
    assert plain.status_code == 422 and "ishlamaydi" in plain.json()["detail"]
    denied = _book(client, rec, pid, saturday, "10:00", override_reason="Shoshilinch holat, bemor og'ir")
    assert denied.status_code == 403 and "appointments:override" in denied.json()["detail"]      # sabab bor, ruxsat yo'q
    assert _book(client, admin, pid, saturday, "10:00").status_code == 422                       # ruxsat bor, sabab yo'q
    assert _book(client, admin, pid, saturday, "10:00", override_reason="  yo ").status_code == 422   # juda qisqa
    ok = _book(client, admin, pid, saturday, "10:00", override_reason="Shoshilinch holat, bemor og'ir")
    assert ok.status_code == 201 and ok.json()["override_reason"] == "Shoshilinch holat, bemor og'ir"
    # tanaffus va ish soatidan keyingi vaqt ham shu qoida bilan
    assert _book(client, admin, pid, monday, "13:00", override_reason="Tushlik vaqtida qabul").status_code == 201
    assert _book(client, admin, pid, monday, "18:00", override_reason="Kechki qabul kelishilgan").status_code == 201
    # ish vaqti ichida sabab kerak emas va izi qolmaydi
    normal = _book(client, admin, pid, monday, "10:00", override_reason="kerak emas edi")
    assert normal.status_code == 201 and normal.json()["override_reason"] is None


def test_senior_registrar_can_override_but_conflicts_still_forbidden(client, auth):
    senior = _senior(client, auth)
    p1, p2 = _patient(client, auth, "Bir"), _patient(client, auth, "Ikki")
    saturday = _day(5)
    assert _book(client, senior, p1, saturday, "10:00", override_reason="Kelishilgan qo'shimcha qabul").status_code == 201
    clash = _book(client, senior, p2, saturday, "10:15", override_reason="Yana qo'shimcha qabul")
    assert clash.status_code == 409 and "Shifokor" in clash.json()["detail"]                  # shifokor to'qnashuvi taqiqlangan
    rooms = {r["name"]: r["id"] for r in client.get("/rooms", headers=senior).json()}
    karimova = _doctor_id(client, auth("admin"), "Dr. Zulfiya Karimova")
    room_clash = client.post("/appointments", headers=senior, json={
        "patient_id": p2, "doctor_id": karimova, "date": saturday, "time": "10:00", "type": "Konsultatsiya",
        "room_id": rooms["101"], "override_reason": "Dam olish kuni kelishuv"})
    assert room_clash.status_code == 409 and "Kabinet" in room_clash.json()["detail"]          # kabinet to'qnashuvi taqiqlangan
    assert client.get("/appointments", headers=senior, params={"patient_id": p2}).json() == []


def test_override_audited_with_reason_and_user(client, auth):
    senior = _senior(client, auth)
    pid = _patient(client, auth)
    appt = _book(client, senior, pid, _day(6), "11:00", override_reason="Yakshanba kuni favqulodda").json()
    audit = client.get("/security/audit", params={"entity_type": "appointment", "limit": 50}, headers=auth("admin")).json()["items"]
    ov = [e for e in audit if e["action"] == "override"]
    assert len(ov) == 1 and ov[0]["entity_id"] == appt["id"] and ov[0]["user_name"] == "Katta Registrator"
    assert ov[0]["details"]["reason"] == "Yakshanba kuni favqulodda" and "ishlamaydi" in ov[0]["details"]["violation"]


def test_override_on_reschedule_and_waitlist_and_clearing(client, auth):
    admin, rec = auth("admin"), auth("receptionist")
    pid = _patient(client, auth)
    monday, saturday = _day(0), _day(5)
    appt = _book(client, rec, pid, monday, "10:00").json()
    assert client.patch(f"/appointments/{appt['id']}", headers=rec, json={"date": saturday}).status_code == 422
    assert client.patch(f"/appointments/{appt['id']}", headers=rec,
                        json={"date": saturday, "override_reason": "Bemor boshqa kun kela olmaydi"}).status_code == 403
    moved = client.patch(f"/appointments/{appt['id']}", headers=admin,
                         json={"date": saturday, "override_reason": "Bemor boshqa kun kela olmaydi"}).json()
    assert moved["date"] == saturday and moved["override_reason"] == "Bemor boshqa kun kela olmaydi"
    back = client.patch(f"/appointments/{appt['id']}", headers=admin, json={"date": monday}).json()   # ish vaqtiga qaytdi
    assert back["override_reason"] is None
    # kutish ro'yxatidan
    entry = client.post("/waitlist", headers=rec, json={"patient_id": _patient(client, auth, "Kutuvchi"), "doctor": DOC,
                                                       "date_from": monday}).json()
    assert client.post(f"/waitlist/{entry['id']}/book", headers=rec, json={"date": saturday, "time": "10:00"}).status_code == 422
    booked = client.post(f"/waitlist/{entry['id']}/book", headers=admin,
                         json={"date": saturday, "time": "10:00", "override_reason": "Kutuvchiga dam olish kuni"})
    assert booked.status_code == 201 and booked.json()["override_reason"] == "Kutuvchiga dam olish kuni"
    assert client.get("/waitlist", params={"status": "Booked"}, headers=rec).json()[0]["id"] == entry["id"]


def test_vacation_also_overridable_but_vacation_is_checked_first(client, auth):
    admin = auth("admin")
    sid = _doctor_id(client, admin)
    pid = _patient(client, auth)
    monday = _day(0)
    client.post(f"/staff/{sid}/schedule/exceptions", headers=admin, json={
        "kind": "Vacation", "date_from": monday, "date_to": (date.fromisoformat(monday) + timedelta(days=4)).isoformat()})
    assert _book(client, auth("receptionist"), pid, monday, "10:00").status_code == 422
    assert _book(client, admin, pid, monday, "10:00", override_reason="Shifokor ta'ildan chaqirildi").status_code == 201
