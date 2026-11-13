import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.models import Appointment, Message, TelegramLink
from app.schemas.enums import MessageStatus
from app.services import links, messaging, reminders
from tests.test_patients import NEW
from tests.test_schedule import _day

DOC = "Dr. Behruz Rustamov"   # Du-Ju 09:00-17:00
TZ = timedelta(hours=5)


@pytest.fixture(autouse=True)
def _clear():
    messaging.MockSmsAdapter.SENT.clear()
    messaging.MockTelegramAdapter.SENT.clear()


def _utc(day: str, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(date.fromisoformat(day), datetime.min.time(), tzinfo=UTC) + timedelta(hours=hh, minutes=mm) - TZ


def _book(client, auth, at="10:00", day=None, consent=("SMS",), language="uz", name="Eslatma Bemor"):
    day = day or _day(0)
    admin = auth("admin")
    pid = client.post("/patients", json={**NEW, "name": name, "phone": "+998 90 555 66 77"}, headers=admin).json()["id"]
    client.put(f"/patients/{pid}/language", headers=admin, json={"language": language})
    for ch in consent:
        client.put(f"/patients/{pid}/consents", headers=admin, json={"channel": ch, "granted": True})
    appt = client.post("/appointments", headers=admin, json={"patient_id": pid, "doctor": DOC, "date": day, "time": at, "type": "Konsultatsiya",
                                                            "override_reason": "Eslatma sinovi uchun"})
    assert appt.status_code == 201, appt.text
    return pid, appt.json(), day


def _sync(now):
    with SessionLocal() as db:
        stats = reminders.schedule_reminders(db, now=now)
        sent = messaging.dispatch_due(db, now=now)
    return stats, sent


def test_24h_and_2h_reminders_sent_once_with_signed_link(client, auth):
    pid, appt, day = _book(client, auth, "10:00")
    start = _utc(day, 10)
    assert _sync(start - timedelta(hours=25))[0] == {"queued": 0, "skipped": 0, "existing": 0}      # hali erta
    stats, sent = _sync(start - timedelta(hours=24) + timedelta(minutes=1))                          # 09:59 oldingi kun
    assert stats["queued"] == 1 and sent["sent"] == 1
    to, body = messaging.MockSmsAdapter.SENT[0]
    assert to == "+998905556677" and "Eslatma" in body and "10:00" in body and DOC in body and "/p/a/" in body
    token = body.split("/p/a/")[1].split()[0]
    assert links.read_token(token, "appt")["id"] == appt["id"]                                       # havola qabulga bog'langan
    assert _sync(start - timedelta(hours=24) + timedelta(minutes=6))[0]["queued"] == 0               # takror yaratilmaydi
    stats, sent = _sync(start - timedelta(hours=2))
    assert stats["queued"] == 1 and sent["sent"] == 1 and "2 soatdan keyin" in messaging.MockSmsAdapter.SENT[1][1]
    assert _sync(start - timedelta(hours=1))[0]["queued"] == 0
    with SessionLocal() as db:
        kinds = sorted(m.kind for m in db.query(Message).filter(Message.appointment_id == uuid.UUID(appt["id"])))
        assert kinds == ["reminder_24h", "reminder_2h"]


def test_no_consent_logged_as_skipped_and_never_sent(client, auth):
    _, appt, day = _book(client, auth, "10:00", consent=())
    stats, sent = _sync(_utc(day, 10) - timedelta(hours=23))
    assert stats["skipped"] == 1 and sent["sent"] == 0 and messaging.MockSmsAdapter.SENT == []
    with SessionLocal() as db:
        m = db.query(Message).filter(Message.appointment_id == uuid.UUID(appt["id"])).one()
        assert m.status == MessageStatus.skipped and "rozilik" in m.skip_reason


def test_quiet_hours_defer_2h_reminder_to_0800_and_skip_if_after_start(client, auth):
    _, appt1, day = _book(client, auth, "08:30", name="Erta Bemor")                                   # 2 soat oldin 06:30 = tun
    _sync(_utc(day, 8, 30) - timedelta(hours=24) + timedelta(minutes=1))                              # 24h: 08:29 oldingi kun (kunduz)
    messaging.MockSmsAdapter.SENT.clear()
    with SessionLocal() as db:
        reminders.schedule_reminders(db, now=_utc(day, 6, 30))
        m = db.query(Message).filter(Message.kind == "reminder_2h", Message.appointment_id == uuid.UUID(appt1["id"])).one()
        assert m.scheduled_at == _utc(day, 8, 0) and m.status == MessageStatus.queued                  # ertalab 08:00 (qabuldan 30 daqiqa oldin)
        db.commit()
        assert messaging.dispatch_due(db, now=_utc(day, 7, 0))["sent"] == 0
        assert messaging.dispatch_due(db, now=_utc(day, 8, 0))["sent"] == 1
    # 07:00 qabul: 08:00 ga surilgan eslatma qabuldan keyin bo'lib qoladi -> o'tkazib yuboriladi
    _, appt2, day2 = _book(client, auth, "07:00", day=_day(1), name="Juda Erta")
    with SessionLocal() as db:
        reminders.schedule_reminders(db, now=_utc(day2, 5, 0))
        m = db.query(Message).filter(Message.kind == "reminder_2h", Message.appointment_id == uuid.UUID(appt2["id"])).one()
        assert m.scheduled_at == _utc(day2, 8, 0)
        db.commit()
        assert messaging.dispatch_due(db, now=_utc(day2, 8, 0))["skipped"] == 2        # 24 soatlik va 2 soatlik: ikkalasi ham qabuldan keyinga qoladi
        db.refresh(m)
        assert "faol emas" in m.skip_reason


def test_cancelled_appointment_reminder_not_sent(client, auth):
    _, appt, day = _book(client, auth, "10:00")
    start = _utc(day, 10)
    with SessionLocal() as db:
        reminders.schedule_reminders(db, now=start - timedelta(hours=24) + timedelta(minutes=1))
        db.commit()
    client.patch(f"/appointments/{appt['id']}/status", params={"status": "Cancelled"}, headers=auth("admin"))
    with SessionLocal() as db:
        assert messaging.dispatch_due(db, now=start - timedelta(hours=24) + timedelta(minutes=2))["skipped"] == 1
        reminders.schedule_reminders(db, now=start - timedelta(hours=2))                              # bekor qilingan qabul uchun yangi eslatma yo'q
        assert db.query(Message).filter(Message.kind == "reminder_2h").count() == 0
    assert messaging.MockSmsAdapter.SENT == []


def test_russian_template_and_telegram_preferred_when_linked_and_consented(client, auth):
    pid, appt, day = _book(client, auth, "10:00", consent=("SMS", "Telegram"), language="ru")
    with SessionLocal() as db:
        db.add(TelegramLink(patient_id=uuid.UUID(pid), chat_id="777001", phone="+998905556677", verified_at=datetime.now(UTC)))
        db.commit()
    _sync(_utc(day, 10) - timedelta(hours=24) + timedelta(minutes=1))
    assert messaging.MockSmsAdapter.SENT == []                                                        # Telegram bor: SMS xarajati yo'q
    chat, body = messaging.MockTelegramAdapter.SENT[0]
    assert chat == "777001" and "завтра" in body and "10:00" in body
    stats = client.get("/messages/stats", headers=auth("admin")).json()
    assert stats["telegram_messages"] == 1 and stats["sms_messages"] == 0 and stats["sms_segments"] == 0


def test_short_notice_booking_gets_only_2h_reminder(client, auth):
    _, appt, day = _book(client, auth, "10:00")
    start = _utc(day, 10)
    with SessionLocal() as db:
        db.execute(text("update appointments set created_at = :c where id = :i"), {"c": start - timedelta(hours=5), "i": appt["id"]})
        db.commit()
        reminders.schedule_reminders(db, now=start - timedelta(hours=3))
        assert [m.kind for m in db.query(Message).filter(Message.appointment_id == uuid.UUID(appt["id"]))] == []
        reminders.schedule_reminders(db, now=start - timedelta(hours=2))
        assert [m.kind for m in db.query(Message).filter(Message.appointment_id == uuid.UUID(appt["id"]))] == ["reminder_2h"]
        assert db.query(Appointment).count() >= 1


def test_signed_links_tamper_purpose_and_expiry():
    soon = datetime.now(UTC) + timedelta(hours=1)
    token = links.make_token("appt", {"id": "abc"}, soon)
    assert links.read_token(token, "appt") == {"id": "abc"}
    assert links.read_token(token, "other") is None                                                   # maqsad boshqa
    body, sig = token.split(".")
    assert links.read_token(body + "." + sig[:-2] + "AA", "appt") is None                             # imzo buzilgan
    assert links.read_token(body[:-2] + "AA." + sig, "appt") is None                                  # ma'lumot o'zgartirilgan
    assert links.read_token("garbage", "appt") is None and links.read_token("", "appt") is None and links.read_token("a.b", "appt") is None
    assert links.read_token(links.make_token("appt", {"id": "x"}, datetime.now(UTC) - timedelta(seconds=5)), "appt") is None   # muddati tugagan
