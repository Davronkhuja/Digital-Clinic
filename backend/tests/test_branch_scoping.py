"""Filial bo'yicha ajratish (v1.9.7): operatsion ro'yxatlar, kassa va xabarlar filialga tegishli; bemor bazasi va bemor tarixi umumiy."""
import pytest

from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")


def _on(h, branch_id):
    return {**h, "X-Branch-Id": branch_id}


def _names(rows, key="name"):
    return [r[key] for r in rows]


@pytest.fixture
def two(client, auth):
    admin = auth("admin")
    b = client.post("/branches", json={"name": "Ikkinchi filial"}, headers=admin).json()
    return admin, _on(admin, b["id"]), b["id"]


def test_staff_and_appointments_are_per_branch_but_patient_history_is_shared(client, auth, two):
    admin, other, bid = two
    assert "Dr. Behruz Rustamov" in _names(client.get("/staff", headers=admin).json())
    assert client.get("/staff", headers=other).json() == []                                   # yangi filialda xodim yo'q
    doc = client.post("/users", headers=admin, json={"name": "Dr. Filial Shifokor", "email": "fd@clinic.uz", "password": "password123",
                                                      "role": "doctor", "branch_id": bid}).json()
    assert _names(client.get("/staff", headers=other).json()) == ["Dr. Filial Shifokor"] and doc["branch"] == "Ikkinchi filial"
    assert "Dr. Filial Shifokor" not in _names(client.get("/staff", headers=admin).json())
    pid = client.post("/patients", json={**NEW, "name": "Umumiy Bemor"}, headers=admin).json()["id"]
    assert client.get("/patients", params={"search": "Umumiy"}, headers=other).json()[0]["id"] == pid      # bemor bazasi umumiy
    appt = client.post("/appointments", headers=other, json={"patient_id": pid, "doctor": "Dr. Filial Shifokor", "date": "2030-01-14", "time": "10:00",
                                                             "type": "Konsultatsiya", "override_reason": "jadvalsiz test"})
    assert appt.status_code == 201, appt.text
    assert len(client.get("/appointments", headers=other).json()) == 1
    assert all(a["doctor"] != "Dr. Filial Shifokor" for a in client.get("/appointments", headers=admin).json())       # asosiy filial ro'yxatida yo'q
    assert len(client.get("/appointments", params={"patient_id": pid}, headers=admin).json()) == 1               # bemor tarixi: filialdan qat'i nazar


def test_invoices_shifts_transactions_and_summary_are_per_branch(client, auth, two):
    admin, other, bid = two
    tx_before = len(client.get("/finance/transactions", headers=admin).json())
    svc = client.post("/services", headers=admin, json={"name": "Filial xizmati", "price": 112000, "mxik": "09302001001000000",
                                                       "package_code": "1500364", "vat_percent": 12}).json()["id"]
    pid = client.post("/patients", json={**NEW, "name": "Kassa Bemor"}, headers=admin).json()["id"]
    inv = client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "lines": [{"service_id": svc, "quantity": 1}], "issue": True}).json()
    assert client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json={"method": "Cash"}).status_code == 201
    assert _names(client.get("/invoices", headers=admin).json(), "number") == [inv["number"]]
    assert client.get("/invoices", headers=other).json() == []                                              # boshqa filialda yo'q
    assert len(client.get("/finance/transactions", headers=admin).json()) == tx_before + 1 and client.get("/finance/transactions", headers=other).json() == []
    assert client.get("/finance/summary", params={"period": "all"}, headers=admin).json()["total_income"] >= 112000
    empty = client.get("/finance/summary", params={"period": "all"}, headers=other).json()
    assert (empty["total_income"], empty["total_expense"], empty["transactions_count"]) == (0, 0, 0)
    assert client.get("/cash-shifts", headers=other).json() == []                                           # smenalar filial bo'yicha
    assert len(client.get("/cash-shifts", headers=admin).json()) >= 1
    new_inv = client.post("/invoices", headers=other, json={"patient_id": pid, "lines": [{"service_id": svc, "quantity": 1}], "issue": True}).json()
    assert new_inv["number"] != inv["number"] and _names(client.get("/invoices", headers=other).json(), "number") == [new_inv["number"]]   # yozuv faol filialga


def test_messages_waitlist_lab_and_emr_lists_are_per_branch(client, auth, two):
    admin, other, bid = two
    pid = client.post("/patients", json={**NEW, "name": "Aloqa Bemor"}, headers=admin).json()["id"]
    client.put(f"/patients/{pid}/consents", headers=admin, json={"channel": "SMS", "granted": True})
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import Branch
    from app.services import messaging
    with SessionLocal() as db:
        main = db.scalar(select(Branch.id).where(Branch.is_default.is_(True)))
        messaging.enqueue(db, branch_id=main, kind="booking_confirmation", body="Salom", patient=db.get(__import__("app.models", fromlist=["Patient"]).Patient, pid),
                          dedupe_key="scope-test")
        db.commit()
    assert len(client.get("/messages", headers=admin).json()) == 1 and client.get("/messages", headers=other).json() == []
    assert client.get("/messages/stats", headers=other).json()["by_status"] == {}
    assert client.get("/messages/stats", headers=admin).json()["by_status"] != {}
    order = client.post("/lab/orders", headers=admin, json={"patient_id": pid, "doctor": "Dr. Behruz Rustamov",
                                                           "test_ids": [client.get("/lab/tests", headers=admin).json()[0]["id"]]}).json()
    assert [o["id"] for o in client.get("/lab/orders", headers=admin).json()] == [order["id"]] and client.get("/lab/orders", headers=other).json() == []
    assert [o["id"] for o in client.get("/lab/orders", params={"patient_id": pid}, headers=other).json()] == [order["id"]]     # bemor tarixi umumiy
    assert client.get("/waitlist", headers=other).json() == []
    assert client.get("/emr", headers=other).json() == []
