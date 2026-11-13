from datetime import UTC, date, datetime, timedelta

import pytest

from app.db.session import SessionLocal
from app.models import Message
from app.schemas.enums import MessageStatus
from app.services import messaging, recalls
from tests.test_patients import NEW
from tests.test_schedule import _day

DOC = "Dr. Behruz Rustamov"
TZ = timedelta(hours=5)


@pytest.fixture(autouse=True)
def _clear():
    messaging.MockSmsAdapter.SENT.clear()


def test_patient_source_validated_stored_and_summarised(client, auth):
    admin = auth("admin")
    for src in ("reklama", "tavsiya", "instagram", "onlayn", "boshqa"):
        res = client.post("/patients", json={**NEW, "name": f"Manba {src}", "source": src}, headers=admin)
        assert res.status_code == 201 and res.json()["source"] == src
    assert client.post("/patients", json={**NEW, "name": "Noto'g'ri", "source": "televizor"}, headers=admin).status_code == 422
    plain = client.post("/patients", json={**NEW, "name": "Manbasiz"}, headers=admin).json()
    assert plain["source"] is None
    upd = client.put(f"/patients/{plain['id']}", json={"source": "instagram"}, headers=admin)
    assert upd.status_code == 200 and upd.json()["source"] == "instagram"
    assert client.put(f"/patients/{plain['id']}", json={"source": ""}, headers=admin).json()["source"] is None      # bo'sh: tozalash
    summary = client.get("/patients/sources", headers=auth("receptionist")).json()
    assert summary["reklama"] == 1 and summary["instagram"] == 1 and summary["ko'rsatilmagan"] >= 1


def _encounter(client, auth, recall_days, consent=True, visit=None):
    admin, doc = auth("admin"), auth("doctor")
    pid = client.post("/patients", json={**NEW, "name": "Qayta Bemor", "phone": "+998 90 777 88 99"}, headers=admin).json()["id"]
    if consent:
        client.put(f"/patients/{pid}/consents", headers=admin, json={"channel": "SMS", "granted": True})
    visit = visit or date.today().isoformat()
    body = {"patient_id": pid, "doctor": DOC, "diagnosis": "Qayta", "prescription": "-", "visit_date": visit}
    if recall_days:
        body["recall_days"] = recall_days
    res = client.post("/emr", headers=doc, json=body)
    assert res.status_code == 201, res.text
    return pid, res.json(), date.fromisoformat(visit)


def test_recall_date_set_updated_and_cleared(client, auth):
    _, enc, visit = _encounter(client, auth, 14)
    assert enc["recall_date"] == (visit + timedelta(days=14)).isoformat()
    doc = auth("doctor")
    upd = client.put(f"/emr/{enc['id']}", headers=doc, json={"recall_days": 30}).json()
    assert upd["recall_date"] == (visit + timedelta(days=30)).isoformat()
    assert client.put(f"/emr/{enc['id']}", headers=doc, json={"recall_days": None}).json()["recall_date"] is None
    assert client.put(f"/emr/{enc['id']}", headers=doc, json={"recall_days": 0}).status_code == 422
    assert client.post("/emr", headers=doc, json={"patient_id": enc["patient_id"], "doctor": DOC, "diagnosis": "x", "prescription": "-",
                                                  "visit_date": "2026-12-01", "recall_days": 731}).status_code == 422


def _local(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=hh, minutes=mm) - TZ


def test_recall_sent_on_the_day_at_10_with_booking_link_once(client, auth):
    pid, enc, visit = _encounter(client, auth, 14)
    due_day = visit + timedelta(days=14)
    with SessionLocal() as db:
        assert recalls.schedule_recalls(db, now=_local(due_day - timedelta(days=1), 12))["queued"] == 0         # hali erta
        stats = recalls.schedule_recalls(db, now=_local(due_day, 7, 0))                                           # tong
        assert stats["queued"] == 1
        m = db.query(Message).filter(Message.kind == "recall").one()
        assert m.scheduled_at == _local(due_day, 10, 0) and "/p/book" in m.body and DOC in m.body
        assert recalls.schedule_recalls(db, now=_local(due_day, 8))["existing"] == 1                              # dedupe
        db.commit()
        assert messaging.dispatch_due(db, now=_local(due_day, 9, 59))["sent"] == 0
        assert messaging.dispatch_due(db, now=_local(due_day, 10, 0))["sent"] == 1
    assert messaging.MockSmsAdapter.SENT[0][0] == "+998907778899"
    with SessionLocal() as db:
        assert recalls.schedule_recalls(db, now=_local(due_day + timedelta(days=3), 12))["existing"] == 1        # qayta yuborilmaydi
    assert pid


def test_recall_not_needed_when_patient_already_booked_or_no_consent_or_no_recall(client, auth):
    pid, enc, visit = _encounter(client, auth, 14)
    due_day = visit + timedelta(days=14)
    appt = client.post("/appointments", headers=auth("admin"), json={"patient_id": pid, "doctor": DOC, "date": _day(0), "time": "10:00", "type": "Konsultatsiya"})
    assert appt.status_code == 201
    with SessionLocal() as db:
        stats = recalls.schedule_recalls(db, now=_local(due_day, 8))
        assert stats["not_needed"] == 1 and stats["queued"] == 0
    # roziligi yo'q: Skipped yoziladi, yuborilmaydi
    _, _, visit2 = _encounter(client, auth, 7, consent=False)
    with SessionLocal() as db:
        stats = recalls.schedule_recalls(db, now=_local(visit2 + timedelta(days=7), 8))
        assert stats["skipped"] == 1
        assert db.query(Message).filter(Message.kind == "recall", Message.status == MessageStatus.skipped).count() == 1
        messaging.dispatch_due(db, now=_local(visit2 + timedelta(days=7), 12))
    assert messaging.MockSmsAdapter.SENT == []
    # recall belgilanmagan ko'rik: eslatma yaratilmaydi
    _, plain, _ = _encounter(client, auth, None)
    with SessionLocal() as db:
        recalls.schedule_recalls(db, now=_local(date.today() + timedelta(days=400), 12))
        assert db.query(Message).filter(Message.dedupe_key == f"recall:{plain['id']}").count() == 0
