"""Shifokor bir nechta filialda (v1.9.17): jadval va istisnolar filial bo'yicha, bir vaqtda ikki filialda jadval taqiqlangan."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models import DoctorSchedule, ScheduleException, Staff
from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"        # asosiy filialda Du-Ju (dushanba-juma) 09:00-17:00, tanaffus 13:00-14:00
ZERO = "00000000-0000-0000-0000-000000000000"


def _on(h, bid):
    return {**h, "X-Branch-Id": bid}


def _monday():
    d = date.today() + timedelta(days=7)
    return d + timedelta(days=(0 - d.weekday()) % 7)


@pytest.fixture
def world(client, auth):
    admin = auth("admin")
    b = client.post("/branches", json={"name": "Ikkinchi klinika"}, headers=admin).json()["id"]
    doc = next(s for s in client.get("/staff", headers=admin).json() if s["name"] == DOC)["id"]
    assert client.put(f"/staff/{doc}/branches", json={"branch_ids": [b]}, headers=admin).status_code == 200
    return admin, _on(admin, b), b, doc


def _day(weekday, start, end, bs=None, be=None):
    return {"weekday": weekday, "start_time": start, "end_time": end, "break_start": bs, "break_end": be}


def test_membership_lists_and_removal_rules(client, auth, world):
    admin, other, b, doc = world
    assert [x["name"] for x in client.get("/staff", params={"role": "Doctor"}, headers=other).json()] == [DOC]          # ikkinchi filialda ham ko'rinadi
    assert DOC in [x["name"] for x in client.get("/staff", headers=admin).json()]
    brs = client.get(f"/staff/{doc}/branches", headers=admin).json()
    assert len(brs) == 2 and [x["home"] for x in brs].count(True) == 1
    assert client.put(f"/staff/{doc}/branches", json={"branch_ids": [ZERO]}, headers=admin).status_code == 422
    assert client.put(f"/staff/{doc}/branches", json={"branch_ids": [b]}, headers=auth("nurse")).status_code == 403
    pid = client.post("/patients", json={**NEW, "name": "Filial Qabul"}, headers=admin).json()["id"]
    appt = client.post("/appointments", headers=other, json={"patient_id": pid, "doctor": DOC, "date": _monday().isoformat(), "time": "10:00",
                                                             "type": "Konsultatsiya", "override_reason": "ikkinchi filial testi"})
    assert appt.status_code == 201
    only_home = client.put(f"/staff/{doc}/branches", json={"branch_ids": [next(x["id"] for x in brs if x["home"])]}, headers=admin)
    assert only_home.status_code == 409                                                                                 # ikkinchi filialda qabul bor
    client.patch(f"/appointments/{appt.json()['id']}/status", params={"status": "Cancelled"}, headers=other)
    assert client.put(f"/staff/{doc}/branches", json={"branch_ids": []}, headers=admin).status_code == 422             # kamida bitta
    assert len(client.put(f"/staff/{doc}/branches", json={"branch_ids": [next(x["id"] for x in brs if x["home"])]}, headers=admin).json()) == 1
    assert client.get("/staff", params={"role": "Doctor"}, headers=other).json() == []


def test_schedules_are_per_branch_and_cannot_overlap_across_branches(client, auth, world):
    admin, other, b, doc = world
    main_days = client.get(f"/staff/{doc}/schedule", headers=admin).json()["days"]
    assert [d["weekday"] for d in main_days] == [0, 1, 2, 3, 4] and client.get(f"/staff/{doc}/schedule", headers=other).json()["days"] == []            # ikkinchi filialda hali shablon yo'q
    ok = client.put(f"/staff/{doc}/schedule", headers=other, json={"days": [_day(0, "18:00:00", "20:00:00"), _day(5, "09:00:00", "12:00:00")]})
    assert ok.status_code == 200 and [d["weekday"] for d in ok.json()["days"]] == [0, 5] and ok.json()["branch_id"] == b
    assert [d["weekday"] for d in client.get(f"/staff/{doc}/schedule", headers=admin).json()["days"]] == [0, 1, 2, 3, 4]   # asosiyniki o'zgarmadi
    bad = client.put(f"/staff/{doc}/schedule", headers=other, json={"days": [_day(0, "16:00:00", "19:00:00")]})          # asosiyda 09-17 bilan kesishadi
    assert bad.status_code == 409 and "boshqa filialda" in bad.json()["detail"]
    assert [d["weekday"] for d in client.get(f"/staff/{doc}/schedule", headers=other).json()["days"]] == [0, 5]            # xato bo'lsa eskisi qoladi
    touching = client.put(f"/staff/{doc}/schedule", headers=other, json={"days": [_day(0, "17:00:00", "20:00:00")]})     # 17:00 da tugaydi: kesishmaydi
    assert touching.status_code == 200
    again = client.put(f"/staff/{doc}/schedule", headers=admin, json={"days": [_day(0, "09:00:00", "18:30:00")]})        # asosiyni uzaytirish: ikkinchi bilan kesishadi
    assert again.status_code == 409
    # DB cheklovi ham himoya qiladi (API'ni chetlab o'tganda)
    with SessionLocal() as db, pytest.raises(IntegrityError):
        staff = db.get(Staff, doc)
        db.add(DoctorSchedule(staff_id=doc, branch_id=b, weekday=1, start_time=staff and __import__("datetime").time(10, 0),
                              end_time=__import__("datetime").time(11, 0)))
        db.flush()
    assert client.put(f"/staff/{doc}/schedule", headers=auth("nurse"), json={"days": []}).status_code == 403


def test_exceptions_per_branch_all_branches_and_extra_work_cross_check(client, auth, world):
    admin, other, b, doc = world
    client.put(f"/staff/{doc}/schedule", headers=other, json={"days": [_day(0, "18:00:00", "20:00:00")]})
    mon = _monday().isoformat()
    vac = client.post(f"/staff/{doc}/schedule/exceptions", headers=admin, json={"kind": "Vacation", "date_from": mon})        # faqat asosiy filial
    assert vac.status_code == 201
    assert len(client.get(f"/staff/{doc}/schedule", headers=admin).json()["exceptions"]) == 1
    assert client.get(f"/staff/{doc}/schedule", headers=other).json()["exceptions"] == []
    assert client.delete(f"/staff/{doc}/schedule/exceptions/{vac.json()['id']}", headers=other).status_code == 404         # boshqa filialniki emas
    assert client.delete(f"/staff/{doc}/schedule/exceptions/{vac.json()['id']}", headers=admin).status_code == 200
    sick = client.post(f"/staff/{doc}/schedule/exceptions", headers=admin, json={"kind": "Sick", "date_from": mon, "all_branches": True})
    assert sick.status_code == 201
    assert len(client.get(f"/staff/{doc}/schedule", headers=admin).json()["exceptions"]) == 1
    assert len(client.get(f"/staff/{doc}/schedule", headers=other).json()["exceptions"]) == 1                              # hamma filialga qo'yildi
    assert client.post(f"/staff/{doc}/schedule/exceptions", headers=admin,
                       json={"kind": "ExtraWork", "date_from": mon, "start_time": "10:00:00", "end_time": "12:00:00", "all_branches": True}).status_code == 422
    # qo'shimcha ish kuni: boshqa filialdagi ish oynasi bilan kesishsa 409
    tue = (_monday() + timedelta(days=1)).isoformat()
    client.put(f"/staff/{doc}/schedule", headers=other, json={"days": [_day(1, "10:00:00", "12:00:00")]})
    clash = client.post(f"/staff/{doc}/schedule/exceptions", headers=other, json={"kind": "ExtraWork", "date_from": tue, "start_time": "09:00:00", "end_time": "11:00:00"})
    assert clash.status_code == 409 and "boshqa filialda" in clash.json()["detail"]                                         # asosiyda Seshanba 09-17
    sat = (_monday() + timedelta(days=5)).isoformat()
    fine = client.post(f"/staff/{doc}/schedule/exceptions", headers=other, json={"kind": "ExtraWork", "date_from": sat, "start_time": "09:00:00", "end_time": "11:00:00"})
    assert fine.status_code == 201
    dup = client.post(f"/staff/{doc}/schedule/exceptions", headers=admin, json={"kind": "ExtraWork", "date_from": sat, "start_time": "10:00:00", "end_time": "12:00:00"})
    assert dup.status_code == 409                                                                                            # DB cheklovi / ilova tekshiruvi
    with SessionLocal() as db:
        assert len(db.scalars(select(ScheduleException).where(ScheduleException.staff_id == doc)).all()) == 3


def test_booking_slots_and_membership_follow_the_branch(client, auth, world):
    admin, other, b, doc = world
    client.put(f"/staff/{doc}/schedule", headers=other, json={"days": [_day(0, "18:00:00", "20:00:00")]})
    mon = _monday().isoformat()
    slots_b = client.get(f"/staff/{doc}/slots", params={"date": mon, "type": "Konsultatsiya"}, headers=other).json()["slots"]
    slots_a = client.get(f"/staff/{doc}/slots", params={"date": mon, "type": "Konsultatsiya"}, headers=admin).json()["slots"]
    assert slots_b[0]["time"] == "18:00" and slots_b[-1]["end_time"] == "20:00" and all(s["time"] >= "18:00" for s in slots_b)
    assert slots_a[0]["time"] == "09:00" and all(s["time"] < "17:00" for s in slots_a)
    pid = client.post("/patients", json={**NEW, "name": "Ikki Filial"}, headers=admin).json()["id"]
    body = {"patient_id": pid, "doctor": DOC, "date": mon, "type": "Konsultatsiya"}
    assert client.post("/appointments", headers=other, json={**body, "time": "18:30"}).status_code == 201                  # ikkinchi filial oynasi ichida
    assert client.post("/appointments", headers=other, json={**body, "time": "10:00"}).status_code == 422                  # u filialda shu vaqtda ishlamaydi
    assert client.post("/appointments", headers=admin, json={**body, "time": "18:00"}).status_code == 422                  # asosiyda 17:00 gacha
    assert [a["doctor"] for a in client.get("/appointments", params={"date": mon}, headers=other).json()] == [DOC]         # qabul ikkinchi filialga yozilgan
    # shifokor ishlamaydigan filialda majburan ham yozib bo'lmaydi
    third = client.post("/branches", json={"name": "Uchinchi klinika"}, headers=admin).json()["id"]
    res = client.post("/appointments", headers=_on(admin, third), json={**body, "time": "10:00", "override_reason": "majburan yozish urinishi"})
    assert res.status_code == 422 and "bu filialda ishlamaydi" in res.json()["detail"]
    assert client.get(f"/staff/{doc}/slots", params={"date": mon}, headers=_on(admin, third)).json()["slots"] == []


def test_doctor_without_any_template_is_unrestricted_in_each_member_branch(client, auth):
    admin = auth("admin")
    b = client.post("/branches", json={"name": "Cheklovsiz filial"}, headers=admin).json()["id"]
    made = client.post("/users", headers=admin, json={"name": "Dr. Shablonsiz", "email": "free@clinic.uz", "password": "password123", "role": "doctor"}).json()
    staff_id = made["staff_id"]
    client.put(f"/staff/{staff_id}/branches", json={"branch_ids": [b]}, headers=admin)
    mon = _monday().isoformat()
    for h in (admin, _on(admin, b)):
        assert client.get(f"/staff/{staff_id}/slots", params={"date": mon, "type": "Konsultatsiya"}, headers=h).json()["slots"][0]["time"] == "00:00"
    # birinchi shablon qo'yilgach, shablonsiz filialda ishlamaydi
    client.put(f"/staff/{staff_id}/schedule", headers=admin, json={"days": [_day(0, "09:00:00", "12:00:00")]})
    assert client.get(f"/staff/{staff_id}/slots", params={"date": mon}, headers=_on(admin, b)).json()["slots"] == []


def test_moving_a_doctor_changes_home_and_keeps_old_branch_only_if_still_used(client, auth):
    admin = auth("admin")
    b = client.post("/branches", json={"name": "Ko'chish filiali"}, headers=admin).json()["id"]
    main_id = next(x["id"] for x in client.get("/branches", headers=admin).json() if x["is_default"])
    made = client.post("/users", headers=admin, json={"name": "Dr. Ko'chuvchi", "email": "mover@clinic.uz", "password": "password123", "role": "doctor"}).json()
    sid = made["staff_id"]
    client.put(f"/staff/{sid}/schedule", headers=admin, json={"days": [_day(0, "09:00:00", "12:00:00")]})                  # asosiyda jadvali bor
    moved = client.patch(f"/users/{made['id']}", json={"branch_id": b}, headers=admin)
    assert moved.status_code == 200 and moved.json()["branch_id"] == b
    names = {x["id"]: x["home"] for x in client.get(f"/staff/{sid}/branches", headers=admin).json()}
    assert names == {b: True, main_id: False}                                                                            # eski filialda jadvali bor: ishlashda qoladi
    client.put(f"/staff/{sid}/schedule", headers=admin, json={"days": []})                                                # eski filial jadvali olib tashlandi
    back = client.patch(f"/users/{made['id']}", json={"branch_id": main_id}, headers=admin)
    assert back.status_code == 200
    names2 = {x["id"]: x["home"] for x in client.get(f"/staff/{sid}/branches", headers=admin).json()}
    assert names2 == {main_id: True}                                                                                     # B da jadval/qabul yo'q edi: a'zolik olib tashlandi
