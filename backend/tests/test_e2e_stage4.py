"""4-bosqich "Shart"i: haftalik kelmay qolish ulushi Dashboard'da, eslatma yuborilgan va yuborilmagan qabullar kesimida.

Zanjir: onlayn yozilish (OTP, rozilik) -> eslatma (24 soat) -> havola bilan tasdiqlash/bekor qilish -> bo'shagan vaqt kutuvchiga ->
qabullar yakunlanadi/kelmaydi -> haftalik ulush eslatmali va eslatmasiz guruhlarda hisoblanadi."""
import re
from datetime import UTC, date, datetime, timedelta

from app.db.session import SessionLocal
from app.services import messaging, reminders
from tests.test_patients import NEW

DOC = "Dr. Behruz Rustamov"   # Du-Ju 09:00-17:00


def _past_weekdays(n):
    """O'tgan haftadan boshlab n ta ish kuni (dushanba-juma)."""
    d = date.today() - timedelta(days=date.today().weekday() + 7)   # o'tgan dushanba
    return [d + timedelta(days=i) for i in range(n)]


def test_weekly_no_show_rate_split_by_reminder(client, auth):
    messaging.MockSmsAdapter.SENT.clear()
    admin = auth("admin")
    days = _past_weekdays(5)
    monday = days[0].isoformat()

    def week():
        data = client.get("/analytics/no-show", params={"weeks": 4}, headers=auth("doctor")).json()
        return data, next(w for w in data["weeks"] if w["week_start"] == monday)

    _, before = week()                                                # test bazasida oldingi qoldiqlar bo'lishi mumkin
    # 4 bemor: ikkitasiga eslatma yuboriladi (rozilik bor), ikkitasiga yo'q (rozilik yo'q)
    plan = [("A", True, "Completed"), ("B", True, "Completed"), ("C", False, "No Show"), ("D", False, "Completed")]
    for i, (tag, consent, final) in enumerate(plan):
        pid = client.post("/patients", json={**NEW, "name": f"Kelmay {tag}", "phone": f"+998 90 800 00 0{i}"}, headers=admin).json()["id"]
        if consent:
            client.put(f"/patients/{pid}/consents", headers=admin, json={"channel": "SMS", "granted": True})
        appt = client.post("/appointments", headers=admin, json={
            "patient_id": pid, "doctor": DOC, "date": days[i].isoformat(), "time": "10:00", "type": "Konsultatsiya",
            "override_reason": "O'tgan hafta tarixi (e2e)"}).json()
        start = datetime.fromisoformat(appt["starts_at"]).astimezone(UTC)
        with SessionLocal() as db:                                   # 2 soatlik eslatma o'sha paytda yuborilgan edi
            reminders.schedule_reminders(db, now=start - timedelta(hours=1))
            messaging.dispatch_due(db, now=start - timedelta(hours=1))
        client.patch(f"/appointments/{appt['id']}/status", params={"status": final}, headers=admin)
    assert len(messaging.MockSmsAdapter.SENT) == 2                    # faqat rozilik berganlarga
    data, after = week()
    assert after["total"] - before["total"] == 4 and after["no_show"] - before["no_show"] == 1
    for key, total, miss in (("reminded", 2, 0), ("not_reminded", 2, 1)):
        assert after[key]["total"] - before[key]["total"] == total and after[key]["no_show"] - before[key]["no_show"] == miss
    assert len(data["weeks"]) == 4
    assert client.get("/analytics/no-show", headers=auth("receptionist")).status_code == 403
    assert client.get("/analytics/no-show", params={"weeks": 0}, headers=admin).status_code == 422


def test_online_booking_to_reminder_confirm_and_waitlist_chain(client, auth):
    messaging.MockSmsAdapter.SENT.clear()
    admin = auth("admin")
    day = date.today() + timedelta(days=14)
    day = day + timedelta(days=(0 - day.weekday()) % 7)               # dushanba (60 kun ichida)
    # 1. telefon OTP -> onlayn yozilish (rozilik bilan)
    client.post("/public/otp/request", json={"phone": "+998 90 801 00 01", "purpose": "booking"})
    code = re.search(r"\b(\d{6})\b", messaging.MockSmsAdapter.SENT[-1][1]).group(1)
    token = client.post("/public/otp/verify", json={"phone": "+998 90 801 00 01", "purpose": "booking", "code": code}).json()["token"]
    doctor = next(d["id"] for d in client.get("/public/booking/doctors").json() if d["name"] == DOC)
    booked = client.post("/public/booking", json={"token": token, "name": "Zanjir Bemor", "doctor_id": doctor, "type": "Konsultatsiya",
                                                  "date": day.isoformat(), "time": "10:00", "consent_sms": True}).json()
    patient = client.get("/patients", params={"search": "Zanjir"}, headers=admin).json()[0]
    assert patient["source"] == "onlayn"
    # 2. kutuvchi (rozilik bilan)
    waiter = client.post("/patients", json={**NEW, "name": "Kutuvchi Zanjir", "phone": "+998 90 801 00 02"}, headers=admin).json()["id"]
    client.put(f"/patients/{waiter}/consents", headers=admin, json={"channel": "SMS", "granted": True})
    client.post("/waitlist", headers=admin, json={"patient_id": waiter, "doctor": DOC, "date_from": day.isoformat(), "date_to": day.isoformat()})
    # 3. 24 soatlik eslatma -> havola bilan tasdiqlash
    appt = client.get("/appointments", params={"patient_id": patient["id"]}, headers=admin).json()[0]
    start = datetime.fromisoformat(appt["starts_at"]).astimezone(UTC)
    messaging.MockSmsAdapter.SENT.clear()
    with SessionLocal() as db:
        reminders.schedule_reminders(db, now=start - timedelta(hours=1))
        messaging.dispatch_due(db, now=start - timedelta(hours=1))
    reminder = messaging.MockSmsAdapter.SENT[-1][1]
    link = re.search(r"/p/a/(\S+)", reminder).group(1)
    assert client.post(f"/public/appointments/{link}/confirm").json()["confirmed"] is True
    # 4. keyin bemor bekor qiladi -> vaqt bo'shaydi va kutuvchiga taklif ketadi
    messaging.MockSmsAdapter.SENT.clear()
    assert client.post(f"/public/appointments/{link}/cancel").json()["status"] == "Cancelled"
    with SessionLocal() as db:
        assert messaging.dispatch_due(db)["sent"] == 1
    to, offer = messaging.MockSmsAdapter.SENT[-1]
    assert to == "+998908010002" and "/p/o/" in offer
    offer_token = re.search(r"/p/o/(\S+)", offer).group(1)
    assert client.post(f"/public/offers/{offer_token}/book").status_code == 201
    assert client.get("/appointments", params={"patient_id": waiter}, headers=admin).json()[0]["time"] == "10:00"
    assert booked["manage_link"]
    log = {m["kind"]: m["status"] for m in client.get("/messages", headers=admin).json()}
    assert log["reminder_24h"] == "Sent" and log["waitlist_offer"] == "Sent"
    stats = client.get("/messages/stats", headers=admin).json()
    assert stats["sms_messages"] >= 4 and stats["sms_segments"] >= stats["sms_messages"]
