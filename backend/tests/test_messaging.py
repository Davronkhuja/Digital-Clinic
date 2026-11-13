from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Appointment, Message, Patient
from app.schemas.enums import Channel, MessageStatus
from app.services import messaging
from app.services.phone import normalize_phone
from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"
TZ = timedelta(hours=5)   # Asia/Tashkent = UTC+5


@pytest.fixture(autouse=True)
def _clear_mocks():
    messaging.MockSmsAdapter.SENT.clear()
    messaging.MockTelegramAdapter.SENT.clear()


def test_normalize_phone():
    for raw in ("+998 90 123-45-67", "90 123 45 67", "998901234567", "(90)1234567"):
        assert normalize_phone(raw) == "+998901234567"
    for bad in ("", None, "123", "+7 999 123 45 67", "99890123456", "abc"):
        assert normalize_phone(bad) is None


def test_sms_segments_gsm7_vs_ucs2():
    assert messaging.sms_segments("") == 0
    assert messaging.sms_segments("a" * 160) == 1 and messaging.sms_segments("a" * 161) == 2 and messaging.sms_segments("a" * 306) == 2
    assert messaging.sms_segments("a" * 307) == 3
    assert messaging.sms_segments("Ertaga qabul, o'tkazib yubormang!") == 1                 # oddiy apostrof GSM-7
    assert messaging.sms_segments("я" * 70) == 1 and messaging.sms_segments("я" * 71) == 2   # kirill UCS-2
    assert messaging.sms_segments("Qabulʻ" + "a" * 64) == 1 and messaging.sms_segments("Qabulʻ" + "a" * 65) == 2   # ʻ (U+02BB) UCS-2


def test_quiet_hours_shift_to_morning(client):
    with SessionLocal() as db:
        branch = db.scalar(select(Patient.branch_id).limit(1)) or db.scalar(select(Appointment.branch_id).limit(1))
        from app.models import Branch
        branch = db.scalar(select(Branch.id))

        def local(h, m=0, day=10):          # klinika vaqti -> UTC
            return datetime(2026, 12, day, h, m, tzinfo=UTC) - TZ

        assert messaging.quiet_adjust(db, branch, local(12)) == local(12)               # kunduzi o'zgarmaydi
        assert messaging.quiet_adjust(db, branch, local(8, 0)) == local(8, 0)           # 08:00: ruxsat (chegara)
        assert messaging.quiet_adjust(db, branch, local(20, 59)) == local(20, 59)
        assert messaging.quiet_adjust(db, branch, local(21, 0)) == local(8, 0, day=11)  # 21:00 -> ertasi kuni 08:00
        assert messaging.quiet_adjust(db, branch, local(23, 30)) == local(8, 0, day=11)
        assert messaging.quiet_adjust(db, branch, local(3, 15)) == local(8, 0)          # tunda -> shu kuni 08:00
        assert messaging.quiet_adjust(db, branch, local(7, 59)) == local(8, 0)


def _patient(client, auth, phone="+998 90 111 22 33", **kw):
    return client.post("/patients", json={**NEW, "name": "Xabar Bemor", "phone": phone, **kw}, headers=auth("admin")).json()["id"]


def _consent(client, auth, pid, channel="SMS", granted=True):
    return client.put(f"/patients/{pid}/consents", headers=auth("receptionist"), json={"channel": channel, "granted": granted, "note": "Shakl №5"})


def test_consent_api_default_revoked_audit_and_permissions(client, auth):
    pid = _patient(client, auth)
    base = client.get(f"/patients/{pid}/contact-preferences", headers=auth("receptionist")).json()
    assert base["language"] == "uz" and [c["status"] for c in base["consents"]] == ["Revoked", "Revoked"] and base["telegram_linked"] is False
    res = _consent(client, auth, pid).json()
    sms = next(c for c in res["consents"] if c["channel"] == "SMS")
    assert sms["status"] == "Granted" and sms["granted_at"] and sms["source"] == "staff" and sms["note"] == "Shakl №5"
    revoked = _consent(client, auth, pid, granted=False).json()
    sms = next(c for c in revoked["consents"] if c["channel"] == "SMS")
    assert sms["status"] == "Revoked" and sms["revoked_at"]
    assert client.put(f"/patients/{pid}/consents", headers=auth("cashier"), json={"channel": "SMS", "granted": True}).status_code == 403
    assert client.put(f"/patients/{pid}/language", headers=auth("receptionist"), json={"language": "ru"}).json()["language"] == "ru"
    assert client.put(f"/patients/{pid}/language", headers=auth("receptionist"), json={"language": "en"}).status_code == 422
    audit = client.get("/security/audit", params={"entity_type": "consent", "limit": 10}, headers=auth("admin")).json()["items"]
    assert [e["details"]["granted"] for e in audit][:2] == [False, True]


def test_no_consent_means_skipped_never_sent(client, auth):
    pid = _patient(client, auth)
    with SessionLocal() as db:
        patient = db.get(Patient, __import__("uuid").UUID(pid))
        msg = messaging.enqueue(db, branch_id=patient.branch_id, kind="reminder_24h", body="Salom", patient=patient)
        assert msg.status == MessageStatus.skipped and msg.skip_reason
        db.commit()
        assert messaging.dispatch_due(db)["sent"] == 0
    assert messaging.MockSmsAdapter.SENT == []


def test_consent_given_then_sent_and_logged_with_segments(client, auth):
    pid = _patient(client, auth)
    _consent(client, auth, pid)
    with SessionLocal() as db:
        patient = db.get(Patient, __import__("uuid").UUID(pid))
        noon = datetime(2026, 12, 10, 7, 0, tzinfo=UTC)                           # 12:00 Toshkent
        msg = messaging.enqueue(db, branch_id=patient.branch_id, kind="recall", body="Ertaga qabul " + "a" * 200, patient=patient, scheduled_at=noon)
        assert msg.status == MessageStatus.queued and msg.channel == Channel.sms and msg.to_address == "+998901112233"
        db.commit()
        assert messaging.dispatch_due(db, now=noon)["sent"] == 1
        db.refresh(msg)
        assert msg.status == MessageStatus.sent and msg.sent_at and msg.attempts == 1 and msg.sms_segments == 2
    assert messaging.MockSmsAdapter.SENT[0][0] == "+998901112233"
    log = client.get("/messages", headers=auth("receptionist")).json()
    assert log[0]["status"] == "Sent" and log[0]["patient_name"] == "Xabar Bemor"
    stats = client.get("/messages/stats", headers=auth("admin")).json()
    assert stats["sms_messages"] == 1 and stats["sms_segments"] == 2 and stats["by_status"]["Sent"] == 1


def test_consent_revoked_after_queueing_is_skipped_at_send_time(client, auth):
    pid = _patient(client, auth)
    _consent(client, auth, pid)
    with SessionLocal() as db:
        patient = db.get(Patient, __import__("uuid").UUID(pid))
        noon = datetime(2026, 12, 10, 7, 0, tzinfo=UTC)
        msg = messaging.enqueue(db, branch_id=patient.branch_id, kind="recall", body="Salom", patient=patient, scheduled_at=noon)
        db.commit()
        mid = msg.id
    _consent(client, auth, pid, granted=False)
    with SessionLocal() as db:
        assert messaging.dispatch_due(db, now=datetime(2026, 12, 10, 7, 1, tzinfo=UTC))["skipped"] == 1
        m = db.get(Message, mid)
        assert m.status == MessageStatus.skipped and "bekor" in m.skip_reason
    assert messaging.MockSmsAdapter.SENT == []


def test_night_message_deferred_then_sent_in_morning(client, auth):
    pid = _patient(client, auth)
    _consent(client, auth, pid)
    with SessionLocal() as db:
        patient = db.get(Patient, __import__("uuid").UUID(pid))
        night = datetime(2026, 12, 10, 18, 30, tzinfo=UTC)                        # 23:30 Toshkent
        msg = messaging.enqueue(db, branch_id=patient.branch_id, kind="recall", body="Tungi xabar", patient=patient, scheduled_at=night)
        assert msg.scheduled_at == datetime(2026, 12, 11, 3, 0, tzinfo=UTC)       # ertasi kuni 08:00 Toshkent
        db.commit()
        assert messaging.dispatch_due(db, now=night + timedelta(hours=1))["sent"] == 0      # hali erta
        # navbatdagi xabar tunda yuborishga uringanda ham suriladi (sozlama o'zgargan yoki kech qolgan)
        msg.scheduled_at = night
        db.commit()
        assert messaging.dispatch_due(db, now=night)["deferred"] == 1 and msg.scheduled_at == datetime(2026, 12, 11, 3, 0, tzinfo=UTC)
        assert messaging.dispatch_due(db, now=datetime(2026, 12, 11, 3, 0, tzinfo=UTC))["sent"] == 1


def test_retry_with_backoff_then_failed_after_three_attempts(client, auth, monkeypatch):
    pid = _patient(client, auth)
    _consent(client, auth, pid)

    class Broken:
        def send(self, to, text):
            raise messaging.SendError("provayder javob bermadi")

    monkeypatch.setitem(messaging._adapters, Channel.sms, Broken())
    with SessionLocal() as db:
        patient = db.get(Patient, __import__("uuid").UUID(pid))
        t0 = datetime(2026, 12, 10, 7, 0, tzinfo=UTC)
        msg = messaging.enqueue(db, branch_id=patient.branch_id, kind="recall", body="Qayta", patient=patient, scheduled_at=t0)
        db.commit()
        assert messaging.dispatch_due(db, now=t0)["retry"] == 1
        assert msg.attempts == 1 and msg.status == MessageStatus.queued and msg.scheduled_at == t0 + timedelta(minutes=5)
        assert messaging.dispatch_due(db, now=t0 + timedelta(minutes=4))["retry"] == 0           # hali erta
        messaging.dispatch_due(db, now=t0 + timedelta(minutes=5))
        assert msg.attempts == 2 and msg.scheduled_at == t0 + timedelta(minutes=5) + timedelta(minutes=15)
        assert messaging.dispatch_due(db, now=t0 + timedelta(minutes=21))["failed"] == 1
        assert msg.status == MessageStatus.failed and msg.attempts == 3 and "javob bermadi" in msg.last_error and msg.sms_segments == 0


def test_otp_is_transactional_no_consent_no_quiet_hours(client, auth):
    with SessionLocal() as db:
        from app.models import Branch
        branch = db.scalar(select(Branch.id))
        night = datetime(2026, 12, 10, 19, 0, tzinfo=UTC)                         # 00:00 Toshkent
        msg = messaging.enqueue(db, branch_id=branch, kind="otp", body="Kod 123456", patient=None, channel=Channel.sms,
                                to_address="+998901112233", scheduled_at=night)
        assert msg.status == MessageStatus.queued and msg.scheduled_at == night
        db.commit()
        assert messaging.dispatch_due(db, now=night)["sent"] == 1
    assert messaging.MockSmsAdapter.SENT[0][1] == "Kod 123456"
    log = client.get("/messages", params={"kind": "otp"}, headers=auth("admin")).json()[0]
    assert log["body"] != "Kod 123456" and log["to_address"].startswith("***")      # logda OTP yashirilgan


def test_dedupe_key_and_templates_editable_with_validation(client, auth):
    pid = _patient(client, auth)
    _consent(client, auth, pid)
    with SessionLocal() as db:
        patient = db.get(Patient, __import__("uuid").UUID(pid))
        first = messaging.enqueue(db, branch_id=patient.branch_id, kind="recall", body="x", patient=patient, dedupe_key="recall:1")
        assert first is not None
        assert messaging.enqueue(db, branch_id=patient.branch_id, kind="recall", body="x", patient=patient, dedupe_key="recall:1") is None
        db.commit()
    admin = auth("admin")
    tpls = client.get("/message-templates", headers=admin).json()
    assert {(t["key"], t["language"]) for t in tpls} >= {("reminder_24h", "uz"), ("reminder_24h", "ru"), ("otp", "ru")} and all(t["is_default"] for t in tpls)
    assert "{link}" in next(t for t in tpls if t["key"] == "reminder_24h" and t["language"] == "uz")["body"]
    ok = client.put("/message-templates/reminder_2h/uz", headers=admin, json={"body": "{clinic}: {doctor} qabuli {time} da. Bekor: {link}"})
    assert ok.status_code == 200 and ok.json()["is_default"] is False
    assert client.put("/message-templates/reminder_2h/uz", headers=admin, json={"body": "Salom {foydalanuvchi}"}).status_code == 422
    assert client.put("/message-templates/nope/uz", headers=admin, json={"body": "Matn matn"}).status_code == 404
    assert client.put("/message-templates/reminder_2h/uz", headers=auth("doctor"), json={"body": "Matn matn"}).status_code == 403
    with SessionLocal() as db:
        assert messaging.render(db, "reminder_2h", "uz", clinic="K", doctor="D", time="10:00", link="L") == "K: D qabuli 10:00 da. Bekor: L"
        assert "завтра" in messaging.render(db, "reminder_24h", "ru", clinic="K", patient="P", doctor="D", date="1", time="2", link="L")
    assert client.delete("/message-templates/reminder_2h/uz", headers=admin).status_code == 200
    assert next(t for t in client.get("/message-templates", headers=admin).json() if t["key"] == "reminder_2h" and t["language"] == "uz")["is_default"]
