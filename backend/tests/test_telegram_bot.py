import re
import uuid
from datetime import UTC, datetime

import pytest

from app.db.session import SessionLocal
from app.models import TelegramLink
from app.services import messaging, reminders
from app.services import telegram_bot as bot
from tests.test_patients import NEW
from tests.test_schedule import _day

DOC = "Dr. Behruz Rustamov"
PHONE = "+998 90 700 00 01"
CHAT = "5550001"


@pytest.fixture(autouse=True)
def _clear():
    messaging.MockSmsAdapter.SENT.clear()
    messaging.MockTelegramAdapter.SENT.clear()


def _patient(client, auth, name="Bot Bemor", phone=PHONE):
    return client.post("/patients", json={**NEW, "name": name, "phone": phone}, headers=auth("admin")).json()["id"]


def _link(db_call, *args):
    with SessionLocal() as db:
        return db_call(db, *args)


def _full_link(client, auth, phone=PHONE, chat=CHAT, uid=111):
    r = _link(bot.contact, chat, uid, uid, phone)
    assert "SMS" in r.text
    code = re.search(r"\b(\d{6})\b", messaging.MockSmsAdapter.SENT[-1][1]).group(1)
    ok = _link(bot.text, chat, code)
    assert "tasdiqlandi" in ok.text
    return code


def test_start_requires_contact_and_rejects_foreign_contact(client, auth):
    r = _link(bot.start, CHAT)
    assert r.request_contact is True and "telefon" in r.text.lower()
    foreign = _link(bot.contact, CHAT, 111, 999, PHONE)                      # boshqaning kontakti
    assert foreign.request_contact is True and "o'zingizning" in foreign.text
    assert _link(bot.contact, CHAT, 111, None, PHONE).request_contact is True
    assert messaging.MockSmsAdapter.SENT == []
    _patient(client, auth)
    assert "topilmadi" in _link(bot.contact, CHAT, 111, 111, "+998 90 799 99 99").text                 # bunday bemor yo'q
    assert "topilmadi" in _link(bot.contact, CHAT, 111, 111, "123").text
    with SessionLocal() as db:
        assert db.query(TelegramLink).count() == 0


def test_link_flow_with_otp_wrong_code_and_medical_gate(client, auth):
    pid = _patient(client, auth)
    r = _link(bot.contact, CHAT, 111, 111, "+998907000001")
    assert "SMS" in r.text and messaging.MockSmsAdapter.SENT[-1][0] == "+998907000001"
    code = re.search(r"\b(\d{6})\b", messaging.MockSmsAdapter.SENT[-1][1]).group(1)
    # tasdiqlashdan oldin tibbiy ma'lumot va buyruqlar yopiq
    assert _link(bot.results, CHAT).text and "Tasdiqlangan" not in _link(bot.text, CHAT, "/results").text
    assert _link(bot.text, CHAT, "/results").request_contact is True            # hali ulanmagan: telefonni ulash so'raladi
    wrong = "000000" if code != "000000" else "111111"
    assert "noto'g'ri" in _link(bot.text, CHAT, wrong).text.lower()
    with SessionLocal() as db:
        assert db.query(TelegramLink).filter(TelegramLink.verified_at.is_not(None)).count() == 0
    assert "tasdiqlandi" in _link(bot.text, CHAT, code).text
    with SessionLocal() as db:
        link = db.query(TelegramLink).one()
        assert str(link.patient_id) == pid and link.verified_at and link.chat_id == CHAT
    assert "Siz ulangansiz" in _link(bot.start, CHAT).text


def test_consent_commands_and_reminder_goes_to_telegram(client, auth):
    pid = _patient(client, auth)
    _full_link(client, auth)
    prefs = client.get(f"/patients/{pid}/contact-preferences", headers=auth("admin")).json()
    assert prefs["telegram_linked"] is True and next(c for c in prefs["consents"] if c["channel"] == "Telegram")["status"] == "Revoked"   # ulanish = rozilik emas
    assert "rozilik qayd etildi" in _link(bot.text, CHAT, "/consent").text
    tg = next(c for c in client.get(f"/patients/{pid}/contact-preferences", headers=auth("admin")).json()["consents"] if c["channel"] == "Telegram")
    assert tg["status"] == "Granted" and tg["source"] == "bot"
    appt = client.post("/appointments", headers=auth("admin"), json={"patient_id": pid, "doctor": DOC, "date": _day(0), "time": "10:00", "type": "Konsultatsiya"}).json()
    start = datetime.fromisoformat(appt["starts_at"])
    with SessionLocal() as db:
        reminders.schedule_reminders(db, now=start.astimezone(UTC).replace(microsecond=0) - __import__("datetime").timedelta(hours=23))
        messaging.dispatch_due(db, now=start - __import__("datetime").timedelta(hours=23))
    assert messaging.MockTelegramAdapter.SENT and messaging.MockTelegramAdapter.SENT[0][0] == CHAT and "10:00" in messaging.MockTelegramAdapter.SENT[0][1]
    # voz kechish
    assert "voz kechildi" in _link(bot.text, CHAT, "/stop").text
    assert next(c for c in client.get(f"/patients/{pid}/contact-preferences", headers=auth("admin")).json()["consents"] if c["channel"] == "Telegram")["status"] == "Revoked"


def test_appointments_confirm_cancel_buttons(client, auth):
    pid = _patient(client, auth)
    _full_link(client, auth)
    a1 = client.post("/appointments", headers=auth("admin"), json={"patient_id": pid, "doctor": DOC, "date": _day(0), "time": "10:00", "type": "Konsultatsiya"}).json()
    a2 = client.post("/appointments", headers=auth("admin"), json={"patient_id": pid, "doctor": DOC, "date": _day(0), "time": "11:00", "type": "Konsultatsiya"}).json()
    r = _link(bot.text, CHAT, "/appointments")
    assert DOC in r.text and len(r.buttons) == 2 and r.buttons[0][0][1] == f"c:{a1['id']}" and r.buttons[0][1][1] == f"x:{a1['id']}"
    assert "tasdiqlandi" in _link(bot.callback, CHAT, f"c:{a1['id']}").text
    assert "✅" in _link(bot.appointments, CHAT).text.splitlines()[0]
    assert "bekor qilindi" in _link(bot.callback, CHAT, f"x:{a2['id']}").text
    rows = {a["id"]: a for a in client.get("/appointments", params={"patient_id": pid}, headers=auth("admin")).json()}
    assert rows[a1["id"]]["confirmed"] is True and rows[a2["id"]]["status"] == "Cancelled" and rows[a2["id"]]["cancel_source"] == "bot"
    assert "topilmadi" in _link(bot.callback, CHAT, f"x:{a2['id']}").text                       # qayta bekor qilib bo'lmaydi
    assert "topilmadi" in _link(bot.callback, CHAT, "x:not-a-uuid").text
    # boshqa bemorning qabuliga tegib bo'lmaydi
    other = _patient(client, auth, "Begona", "+998 90 700 00 09")
    foreign = client.post("/appointments", headers=auth("admin"), json={"patient_id": other, "doctor": DOC, "date": _day(0), "time": "14:00", "type": "Konsultatsiya"}).json()
    assert "topilmadi" in _link(bot.callback, CHAT, f"x:{foreign['id']}").text
    assert client.get("/appointments", params={"patient_id": other}, headers=auth("admin")).json()[0]["status"] == "Scheduled"


def test_results_only_approved_and_only_after_verification(client, auth):
    pid = _patient(client, auth)
    tests = {t["code"]: t for t in client.get("/lab/tests", headers=auth("doctor")).json()}
    order = client.post("/lab/orders", headers=auth("doctor"), json={"patient_id": pid, "doctor": DOC, "test_ids": [tests["GLU"]["id"]]}).json()
    client.put(f"/lab/orders/{order['id']}/results", headers=auth("doctor"), json={"results": [{"item_id": order["items"][0]["id"], "value": 7.1}]})
    _full_link(client, auth)
    assert "yo'q" in _link(bot.text, CHAT, "/results").text                                     # tasdiqlanmagan
    client.post(f"/lab/orders/{order['id']}/approve", headers=auth("doctor"))
    text = _link(bot.text, CHAT, "/results").text
    assert "Glyukoza" in text and "7.1" in text and "⚠️" in text and "Bot Bemor" in text


def test_family_phone_links_all_patients(client, auth):
    a, b = _patient(client, auth, "Ota Bot"), _patient(client, auth, "Bola Bot")
    _full_link(client, auth)
    with SessionLocal() as db:
        assert {str(x.patient_id) for x in db.query(TelegramLink).filter(TelegramLink.verified_at.is_not(None))} == {a, b}
    assert uuid.UUID(a)


def test_aiogram_transport_module_imports():
    import app.bot as transport

    assert transport.dp is not None and callable(transport.main)
