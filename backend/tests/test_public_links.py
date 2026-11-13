import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.session import SessionLocal
from app.models import Message
from app.schemas.enums import MessageStatus
from app.services import links, messaging
from tests.test_patients import NEW
from tests.test_schedule import _day

DOC = "Dr. Behruz Rustamov"


@pytest.fixture(autouse=True)
def _clear():
    messaging.MockSmsAdapter.SENT.clear()


def _patient(client, auth, name, phone, consent=True):
    admin = auth("admin")
    pid = client.post("/patients", json={**NEW, "name": name, "phone": phone}, headers=admin).json()["id"]
    if consent:
        client.put(f"/patients/{pid}/consents", headers=admin, json={"channel": "SMS", "granted": True})
    return pid


def _book(client, auth, pid, at="10:00", day=None):
    res = client.post("/appointments", headers=auth("admin"), json={"patient_id": pid, "doctor": DOC, "date": day or _day(0), "time": at,
                                                                   "type": "Konsultatsiya"})
    assert res.status_code == 201, res.text
    return res.json()


def _token(appt):
    return links.make_token("appt", {"id": appt["id"]}, datetime.fromisoformat(appt["starts_at"]))


def test_confirm_via_link_shows_minimal_info_and_marks_appointment(client, auth):
    appt = _book(client, auth, _patient(client, auth, "Tasdiq Bemor", "+998 90 100 00 01"))
    token = _token(appt)
    view = client.get(f"/public/appointments/{token}")                 # login talab qilinmaydi
    assert view.status_code == 200
    info = view.json()
    assert info["doctor"] == DOC and info["time"] == "10:00" and info["status"] == "Scheduled" and info["can_act"] is True and info["confirmed"] is False
    assert set(info) == {"clinic", "date", "time", "doctor", "status", "confirmed", "can_act"}      # bemor ismi/tibbiy ma'lumot yo'q
    done = client.post(f"/public/appointments/{token}/confirm").json()
    assert done["confirmed"] is True
    assert client.post(f"/public/appointments/{token}/confirm").json()["confirmed"] is True            # idempotent
    mine = client.get("/appointments", params={"patient_id": appt["patient_id"]}, headers=auth("admin")).json()[0]
    assert mine["confirmed"] is True and mine["status"] == "Scheduled"
    audit = client.get("/security/audit", params={"entity_type": "appointment", "limit": 20}, headers=auth("admin")).json()["items"]
    assert any(e["details"].get("via") == "link" and e["details"].get("confirmed") for e in audit)


def test_invalid_tampered_expired_links_rejected(client, auth):
    appt = _book(client, auth, _patient(client, auth, "Havola Bemor", "+998 90 100 00 02"))
    good = _token(appt)
    body, sig = good.split(".")
    expired = links.make_token("appt", {"id": appt["id"]}, datetime.now(UTC) - timedelta(minutes=1))
    other_purpose = links.make_token("offer", {"id": appt["id"]}, datetime.now(UTC) + timedelta(hours=1))
    for bad in ("garbage", body + "." + sig[:-2] + "AA", expired, other_purpose):
        assert client.get(f"/public/appointments/{bad}").status_code == 410, bad
        assert client.post(f"/public/appointments/{bad}/cancel").status_code == 410
    missing = links.make_token("appt", {"id": str(uuid.uuid4())}, datetime.now(UTC) + timedelta(hours=1))
    assert client.get(f"/public/appointments/{missing}").status_code == 404
    assert client.get("/appointments", params={"patient_id": appt["patient_id"]}, headers=auth("admin")).json()[0]["status"] == "Scheduled"


def test_cancel_via_link_frees_slot_and_blocks_further_actions(client, auth):
    pid = _patient(client, auth, "Bekor Bemor", "+998 90 100 00 03")
    appt = _book(client, auth, pid)
    token = _token(appt)
    res = client.post(f"/public/appointments/{token}/cancel")
    assert res.status_code == 200 and res.json()["status"] == "Cancelled" and res.json()["can_act"] is False
    mine = client.get("/appointments", params={"patient_id": pid}, headers=auth("admin")).json()[0]
    assert mine["status"] == "Cancelled" and mine["cancel_source"] == "link"
    assert client.post(f"/public/appointments/{token}/cancel").status_code == 409
    assert client.post(f"/public/appointments/{token}/confirm").status_code == 409
    other = _patient(client, auth, "Yangi Bemor", "+998 90 100 00 04")
    assert client.post("/appointments", headers=auth("admin"), json={"patient_id": other, "doctor": DOC, "date": _day(0), "time": "10:00",
                                                                     "type": "Konsultatsiya"}).status_code == 201     # vaqt bo'shadi


def _waiter(client, auth, name, phone, consent=True):
    pid = _patient(client, auth, name, phone, consent)
    entry = client.post("/waitlist", headers=auth("admin"), json={"patient_id": pid, "doctor": DOC, "date_from": _day(0), "date_to": _day(0)})
    assert entry.status_code == 201, entry.text
    return pid, entry.json()


def _dispatch():
    with SessionLocal() as db:
        return messaging.dispatch_due(db)


def _offer_token(body):
    return body.split("/p/o/")[1].split()[0]


def test_cancelled_slot_offered_to_first_consenting_waiter_who_can_claim_it(client, auth):
    appt = _book(client, auth, _patient(client, auth, "Bekor Qiluvchi", "+998 90 100 00 05"))
    _, nocontact = _waiter(client, auth, "Rozilik Yo'q", "+998 90 100 00 06", consent=False)        # birinchi, lekin roziligi yo'q
    second_pid, entry = _waiter(client, auth, "Ikkinchi Kutuvchi", "+998 90 100 00 07")
    _waiter(client, auth, "Uchinchi Kutuvchi", "+998 90 100 00 08")
    client.post(f"/public/appointments/{_token(appt)}/cancel")
    stats = _dispatch()
    assert stats["sent"] == 1                                                                      # faqat bitta taklif
    to, body = messaging.MockSmsAdapter.SENT[0]
    assert to == "+998901000007" and "bo'sh vaqt" in body and "10:00" in body and "/p/o/" in body
    token = _offer_token(body)
    info = client.get(f"/public/offers/{token}").json()
    assert info["available"] is True and info["time"] == "10:00" and info["doctor"] == DOC
    booked = client.post(f"/public/offers/{token}/book")
    assert booked.status_code == 201 and booked.json()["time"] == "10:00"
    mine = client.get("/appointments", params={"patient_id": second_pid}, headers=auth("admin")).json()
    assert [(a["time"], a["status"]) for a in mine] == [("10:00", "Scheduled")]
    assert client.get("/waitlist", params={"status": "Booked"}, headers=auth("admin")).json()[0]["id"] == entry["id"]
    assert client.post(f"/public/offers/{token}/book").status_code == 409                          # ikkinchi marta emas
    assert client.get(f"/public/offers/{token}").json()["available"] is False
    assert nocontact


def test_offer_claim_fails_if_slot_taken_meanwhile_and_staff_cancel_also_offers(client, auth):
    appt = _book(client, auth, _patient(client, auth, "Staff Bekor", "+998 90 100 00 09"))
    _waiter(client, auth, "Kutuvchi A", "+998 90 100 00 10")
    client.patch(f"/appointments/{appt['id']}/status", params={"status": "Cancelled"}, headers=auth("admin"))          # xodim bekor qildi
    assert client.get("/appointments", params={"patient_id": appt["patient_id"]}, headers=auth("admin")).json()[0]["cancel_source"] == "staff"
    assert _dispatch()["sent"] == 1
    token = _offer_token(messaging.MockSmsAdapter.SENT[0][1])
    taker = _patient(client, auth, "Ulgurgan Bemor", "+998 90 100 00 11")
    _book(client, auth, taker)                                                                     # vaqtni boshqasi egalladi
    clash = client.post(f"/public/offers/{token}/book")
    assert clash.status_code == 409
    assert client.get("/waitlist", headers=auth("admin")).json()[0]["status"] == "Waiting"          # kutuvchi o'z joyida qoladi


def test_no_offer_without_any_consenting_waiter_and_expired_offer(client, auth):
    appt = _book(client, auth, _patient(client, auth, "Yolg'iz Bemor", "+998 90 100 00 12"))
    _waiter(client, auth, "Rozilik Yo'q 2", "+998 90 100 00 13", consent=False)
    client.post(f"/public/appointments/{_token(appt)}/cancel")
    assert _dispatch()["sent"] == 0 and messaging.MockSmsAdapter.SENT == []
    with SessionLocal() as db:
        assert db.query(Message).filter(Message.kind == "waitlist_offer").count() == 0
    expired = links.make_token("offer", {"entry": str(uuid.uuid4()), "doctor": str(uuid.uuid4()), "starts": datetime.now(UTC).isoformat(), "room": None, "type": "x"},
                               datetime.now(UTC) - timedelta(minutes=1))
    assert client.get(f"/public/offers/{expired}").status_code == 410
    assert client.post(f"/public/offers/{expired}/book").status_code == 410
    assert MessageStatus.queued
