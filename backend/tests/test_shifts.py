import io

from pypdf import PdfReader

from tests.test_patients import NEW


def _issued(client, auth, price=100000, name="Smena Xizmati"):
    admin = auth("admin")
    svc = client.post("/services", headers=admin, json={"name": f"{name} {price}", "price": price, "mxik": "09302001001000000",
                                                       "package_code": "1500364", "vat_percent": 12}).json()
    pid = client.post("/patients", json={**NEW, "name": "Smena Bemor"}, headers=admin).json()["id"]
    return client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "lines": [{"service_id": svc["id"]}], "issue": True}).json()


def _open(client, auth, role="cashier", cash=500000):
    res = client.post("/cash-shifts/open", json={"opening_cash": cash}, headers=auth(role))
    assert res.status_code == 201, res.text
    return res.json()


def test_payment_and_refund_need_open_shift(client, auth):
    inv = _issued(client, auth)
    blocked = client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json={"method": "Cash"})
    assert blocked.status_code == 409 and "smena" in blocked.json()["detail"].lower()
    assert client.get("/cash-shifts/current", headers=auth("cashier")).json() is None
    _open(client, auth)
    pay = client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json={"method": "Cash"}).json()
    assert pay["status"] == "Paid"
    # qaytarish: admin o'z smenasini ochishi kerak
    refuse = client.post(f"/payments/{pay['id']}/refunds", headers=auth("admin"), json={"reason": "Bemor rad etdi", "amount": 10000})
    assert refuse.status_code == 409 and "smena" in refuse.json()["detail"].lower()
    _open(client, auth, "admin", 0)
    assert client.post(f"/payments/{pay['id']}/refunds", headers=auth("admin"), json={"reason": "Bemor rad etdi", "amount": 10000}).status_code == 201


def test_open_validation_one_open_per_user_and_current(client, auth):
    assert client.post("/cash-shifts/open", json={"opening_cash": -1}, headers=auth("cashier")).status_code == 422
    assert client.post("/cash-shifts/open", json={"opening_cash": 100.123}, headers=auth("cashier")).status_code == 422
    assert client.post("/cash-shifts/open", json={}, headers=auth("cashier")).status_code == 201                 # standart 0
    assert client.post("/cash-shifts/open", json={"opening_cash": 5}, headers=auth("cashier")).status_code == 409
    assert client.post("/cash-shifts/open", json={}, headers=auth("doctor")).status_code == 403
    cur = client.get("/cash-shifts/current", headers=auth("cashier")).json()
    assert cur["status"] == "Open" and cur["cashier"] == "Dilfuza Akbarova" and cur["z_number"] is None
    assert client.get("/cash-shifts/current", headers=auth("admin")).json() is None                              # shaxsiy


def test_x_and_z_report_numbers_expected_cash_and_difference(client, auth):
    shift = _open(client, auth, cash=500000)
    _open(client, auth, "admin", 0)
    cashier = auth("cashier")
    a, b, c = _issued(client, auth, 100000), _issued(client, auth, 200000), _issued(client, auth, 50000)
    cash1 = client.post(f"/invoices/{a['id']}/payments", headers=cashier, json={"method": "Cash"}).json()
    client.post(f"/invoices/{b['id']}/payments", headers=cashier, json={"method": "Card"})
    client.post(f"/invoices/{c['id']}/payments", headers=cashier, json={"method": "Cash"})
    client.post(f"/payments/{cash1['id']}/refunds", headers=auth("admin"), json={"reason": "Qisman qaytarish", "amount": 30000})   # admin smenasidan
    x = client.get(f"/cash-shifts/{shift['shift_id']}/report", headers=cashier).json()
    assert x["status"] == "Open" and x["z_number"] is None
    assert (x["cash"]["payments_count"], x["cash"]["payments_total"]) == (2, 150000.0)
    assert (x["card"]["payments_count"], x["card"]["payments_total"]) == (1, 200000.0)
    assert x["cash"]["refunds_total"] == 0.0                                                                      # qaytarish admin smenasida
    assert x["expected_cash"] == 650000.0 and x["sales_total"] == 350000.0
    admin_shift = client.get("/cash-shifts/current", headers=auth("admin")).json()
    assert admin_shift["cash"]["refunds_total"] == 30000.0 and admin_shift["expected_cash"] == -30000.0
    closed = client.post(f"/cash-shifts/{shift['shift_id']}/close", headers=cashier, json={"counted_cash": 640000, "notes": "10 000 kam"})
    assert closed.status_code == 200
    z = closed.json()
    assert z["status"] == "Closed" and z["z_number"].startswith("Z-") and z["closed_at"]
    assert z["expected_cash"] == 650000.0 and z["counted_cash"] == 640000.0 and z["difference"] == -10000.0
    assert z["receipts_missing"] == 0 and z["net_total"] == 350000.0
    # yopilgach hisobot qotgan, yangi to'lovlar unga kirmaydi
    d = _issued(client, auth, 70000)
    assert client.post(f"/invoices/{d['id']}/payments", headers=cashier, json={"method": "Cash"}).status_code == 409
    again = client.get(f"/cash-shifts/{shift['shift_id']}/report", headers=cashier).json()
    assert again["z_number"] == z["z_number"] and again["cash"]["payments_total"] == 150000.0
    assert client.post(f"/cash-shifts/{shift['shift_id']}/close", headers=cashier, json={"counted_cash": 1}).status_code == 409
    # keyingi smena: Z-raqam ketma-ket
    second = _open(client, auth, cash=0)
    z2 = client.post(f"/cash-shifts/{second['shift_id']}/close", headers=cashier, json={"counted_cash": 0}).json()
    assert int(z2["z_number"][2:]) == int(z["z_number"][2:]) + 1 and z2["difference"] == 0.0


def test_surplus_and_validation_on_close(client, auth):
    shift = _open(client, auth, cash=1000)
    cashier = auth("cashier")
    assert client.post(f"/cash-shifts/{shift['shift_id']}/close", headers=cashier, json={"counted_cash": -5}).status_code == 422
    assert client.post(f"/cash-shifts/{shift['shift_id']}/close", headers=cashier, json={}).status_code == 422
    z = client.post(f"/cash-shifts/{shift['shift_id']}/close", headers=cashier, json={"counted_cash": 1500.50}).json()
    assert z["expected_cash"] == 1000.0 and z["difference"] == 500.5


def test_other_cashier_shift_hidden_admin_can_close(client, auth):
    shift = _open(client, auth)
    assert client.get(f"/cash-shifts/{shift['shift_id']}/report", headers=auth("receptionist")).status_code == 403   # finance:read yo'q
    admin_view = client.get(f"/cash-shifts/{shift['shift_id']}/report", headers=auth("admin"))
    assert admin_view.status_code == 200 and admin_view.json()["cashier"] == "Dilfuza Akbarova"
    assert [s["shift_id"] for s in client.get("/cash-shifts", headers=auth("admin")).json()] == [shift["shift_id"]]
    assert client.get("/cash-shifts", headers=auth("cashier")).json()[0]["shift_id"] == shift["shift_id"]
    closed = client.post(f"/cash-shifts/{shift['shift_id']}/close", headers=auth("admin"), json={"counted_cash": 500000})
    assert closed.status_code == 200 and closed.json()["status"] == "Closed"
    audit = client.get("/security/audit", params={"entity_type": "cash_shift", "limit": 20}, headers=auth("admin")).json()["items"]
    closes = [e for e in audit if e["action"] == "update" and e["details"].get("closed")]
    assert closes and closes[0]["details"]["difference"] == "0.00" and closes[0]["user_name"] == "Admin User"


def test_online_payments_not_shift_bound_but_listed_and_missing_receipts_flagged(client, auth, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "payme_merchant_id", "m1")
    shift = _open(client, auth)
    cashier = auth("cashier")
    inv = _issued(client, auth, 80000)
    pay = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Payme"})
    assert pay.status_code == 201 and pay.json()["status"] == "Pending"                           # smena kerak emas, band qilinadi

    inv2 = _issued(client, auth, 60000)
    cash = client.post(f"/invoices/{inv2['id']}/payments", headers=cashier, json={"method": "Cash"}).json()
    from sqlalchemy import text

    from app.db.session import SessionLocal
    with SessionLocal() as db:                                                                     # cheki berilmagan to'lov holati
        db.execute(text("update payments set receipt_status = 'Failed' where id = :i"), {"i": cash["id"]})
        db.commit()
        db.execute(text("update payments set status = 'Paid', paid_at = now(), provider_txn_id = 't1', provider_state = 2 where id = :i"),
                   {"i": pay.json()["id"]})
        db.commit()
    rep = client.get(f"/cash-shifts/{shift['shift_id']}/report", headers=cashier).json()
    assert rep["online"]["payme"] == {"payments_count": 1, "payments_total": 80000.0} and rep["online"]["click"]["payments_count"] == 0
    assert rep["receipts_missing"] == 1 and rep["sales_total"] == 60000.0                          # onlayn kassa sotuviga kirmaydi


def test_z_report_pdf(client, auth):
    shift = _open(client, auth, cash=100000)
    inv = _issued(client, auth, 40000)
    client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json={"method": "Cash"})
    x_pdf = client.get(f"/cash-shifts/{shift['shift_id']}/z-report/pdf", headers=auth("cashier"))
    assert x_pdf.status_code == 200 and x_pdf.content.startswith(b"%PDF")
    assert "X-hisobot" in "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(x_pdf.content)).pages)
    client.post(f"/cash-shifts/{shift['shift_id']}/close", headers=auth("cashier"), json={"counted_cash": 130000})
    z = client.get(f"/cash-shifts/{shift['shift_id']}/z-report/pdf", headers=auth("cashier"))
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(z.content)).pages)
    for needle in ("Z-hisobot", "Z-", "Dilfuza Akbarova", "Kutilgan naqd", "140 000.00", "Sanalgan naqd", "130 000.00", "kamomad", "Digital Clinic"):
        assert needle in text, needle
    assert client.get(f"/cash-shifts/{shift['shift_id']}/z-report/pdf", headers=auth("doctor")).status_code == 403
