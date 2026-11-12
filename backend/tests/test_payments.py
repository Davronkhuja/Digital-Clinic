from decimal import Decimal

from sqlalchemy import text

from app.db.session import SessionLocal
from app.models import InvoiceLine
from app.services import fiscal
from app.services.payments import allocate
from tests.test_patients import NEW


def _line(net):
    return InvoiceLine(net_total=Decimal(str(net)))


def test_allocate_exact_and_proportional():
    lines = [_line(100), _line(200), _line(300)]
    assert [a for _, a in allocate(lines, Decimal("600"))] == [Decimal("100"), Decimal("200"), Decimal("300")]
    parts = [a for _, a in allocate(lines, Decimal("100"))]
    assert sum(parts) == Decimal("100") and parts[0] == Decimal("16.67") and parts[1] == Decimal("33.33")
    third = [a for _, a in allocate([_line(10), _line(10), _line(10)], Decimal("10"))]
    assert sum(third) == Decimal("10") and all(x >= 0 for x in third)


def _issued_invoice(client, auth, price=112000, qty=1, vat=12, name="To'lov Xizmati"):
    admin = auth("admin")
    svc = client.post("/services", headers=admin, json={"name": f"{name} {price}", "price": price, "mxik": "09302001001000000",
                                                       "package_code": "1500364", "vat_percent": vat}).json()
    pid = client.post("/patients", json={**NEW, "name": "To'lovchi"}, headers=admin).json()["id"]
    inv = client.post("/invoices", headers=auth("cashier"), json={"patient_id": pid, "lines": [{"service_id": svc["id"], "quantity": qty}],
                                                                  "issue": True}).json()
    return inv


def test_cash_payment_closes_invoice_with_receipt_and_income(client, auth):
    cashier = auth("cashier")
    inv = _issued_invoice(client, auth)
    res = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"})
    assert res.status_code == 201
    p = res.json()
    assert p["status"] == "Paid" and p["amount"] == 112000.0 and p["receipt_status"] == "Issued" and p["receipt_id"].startswith("MOCK-")
    assert p["paid_at"] and p["created_by"] == "Dilfuza Akbarova"
    after = client.get(f"/invoices/{inv['id']}", headers=cashier).json()
    assert after["status"] == "Paid" and after["paid_amount"] == 112000.0 and after["balance"] == 0.0
    tx = [t for t in client.get("/finance/transactions", params={"type": "income"}, headers=cashier).json() if inv["number"] in t["description"]]
    assert len(tx) == 1 and tx[0]["amount"] == 112000.0 and tx[0]["category"] == "Xizmat to'lovi"
    with SessionLocal() as db:
        row = db.execute(text("select receipt_data->>'total_tiyin', receipt_data->'items'->0->>'mxik', receipt_data->'items'->0->>'vat_tiyin' "
                              "from payments where id = :i"), {"i": p["id"]}).one()
    assert row[0] == "11200000" and row[1] == "09302001001000000" and row[2] == "1200000"       # tiyinda; MXIK, QQS 12000 so'm
    summary = client.get("/finance/summary", params={"period": "all"}, headers=cashier).json()
    assert summary["total_income"] >= 112000.0
    assert client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"}).status_code == 409      # allaqachon to'langan


def test_partial_payments_and_receipt_items_match_payment(client, auth):
    cashier = auth("cashier")
    inv = _issued_invoice(client, auth, price=100000, qty=3)               # 300000
    first = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Card", "amount": 100000, "reference": "TERM-1"}).json()
    mid = client.get(f"/invoices/{inv['id']}", headers=cashier).json()
    assert mid["status"] == "PartiallyPaid" and mid["balance"] == 200000.0 and first["reference"] == "TERM-1"
    assert client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash", "amount": 200000.01}).status_code == 422
    second = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"}).json()                # qoldiq
    assert second["amount"] == 200000.0
    assert client.get(f"/invoices/{inv['id']}", headers=cashier).json()["status"] == "Paid"
    with SessionLocal() as db:
        for pid, expected in ((first["id"], 10000000), (second["id"], 20000000)):
            total, items = db.execute(text("select (receipt_data->>'total_tiyin')::bigint, "
                                           "(select sum((i->>'amount_tiyin')::bigint) from jsonb_array_elements(receipt_data->'items') i) "
                                           "from payments where id = :i"), {"i": pid}).one()
            assert total == items == expected                                  # chek qatorlari yig'indisi to'lovga teng
    payments = client.get(f"/invoices/{inv['id']}/payments", headers=cashier).json()
    assert [p["method"] for p in payments] == ["Card", "Cash"] and payments[0]["receipt_id"] != payments[1]["receipt_id"]


def test_payment_guards(client, auth):
    cashier = auth("cashier")
    admin = auth("admin")
    svc = client.post("/services", headers=admin, json={"name": "Qoralama xizmat", "price": 5000, "mxik": "09302001001000000",
                                                       "package_code": "1", "vat_percent": 0}).json()
    pid = client.post("/patients", json=NEW, headers=admin).json()["id"]
    draft = client.post("/invoices", headers=cashier, json={"patient_id": pid, "lines": [{"service_id": svc["id"]}]}).json()
    assert client.post(f"/invoices/{draft['id']}/payments", headers=cashier, json={"method": "Cash"}).status_code == 409   # Draft
    inv = _issued_invoice(client, auth)
    assert client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Click"}).status_code == 422   # v1.7.4
    assert client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Payme"}).status_code == 503   # sozlanmagan
    assert client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash", "amount": 0}).status_code == 422
    assert client.post(f"/invoices/{inv['id']}/payments", headers=auth("doctor"), json={"method": "Cash"}).status_code == 403
    assert client.get(f"/invoices/{inv['id']}/payments", headers=auth("nurse")).status_code == 403
    client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash", "amount": 1000})
    cancel = client.post(f"/invoices/{inv['id']}/cancel", headers=cashier, json={"reason": "Bekor qilmoqchi"})
    assert cancel.status_code == 409                                                                        # to'lovi bor: qaytarish kerak
    assert client.post(f"/invoices/{draft['id']}/cancel", headers=cashier, json={"reason": "Kerak emas"}).status_code == 200
    assert client.post(f"/invoices/{draft['id']}/payments", headers=cashier, json={"method": "Cash"}).status_code == 409


def test_fiscal_failure_records_nothing(client, auth, monkeypatch):
    cashier = auth("cashier")
    inv = _issued_invoice(client, auth)

    class Broken:
        def sale(self, receipt):
            raise fiscal.FiscalError("operator javob bermadi")

        def refund(self, receipt, original):
            raise fiscal.FiscalError("operator javob bermadi")

    monkeypatch.setattr(fiscal, "_adapter", Broken())
    res = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"})
    assert res.status_code == 502 and "yozilmadi" in res.json()["detail"]
    assert client.get(f"/invoices/{inv['id']}/payments", headers=cashier).json() == []
    assert client.get(f"/invoices/{inv['id']}", headers=cashier).json()["status"] == "Issued"
    assert [t for t in client.get("/finance/transactions", headers=cashier).json() if inv["number"] in t["description"]] == []
    monkeypatch.setattr(fiscal, "_adapter", fiscal.MockFiscalAdapter())
    assert client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"}).status_code == 201     # qayta urinish


def test_refund_requires_permission_updates_status_expense_and_receipt(client, auth):
    cashier, admin = auth("cashier"), auth("admin")
    inv = _issued_invoice(client, auth, price=100000)
    pay = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"}).json()
    assert client.post(f"/payments/{pay['id']}/refunds", headers=cashier, json={"reason": "Bemor rad etdi", "amount": 10000}).status_code == 403
    part = client.post(f"/payments/{pay['id']}/refunds", headers=admin, json={"reason": "Bemor rad etdi", "amount": 30000})
    assert part.status_code == 201
    out = part.json()
    assert out["refunded_amount"] == 30000.0 and out["refunds"][0]["receipt_id"].startswith("MOCK-")
    assert out["refunds"][0]["receipt_id"] != pay["receipt_id"]
    mid = client.get(f"/invoices/{inv['id']}", headers=admin).json()
    assert mid["status"] == "PartiallyPaid" and mid["paid_amount"] == 100000.0 and mid["refunded_amount"] == 30000.0 and mid["balance"] == 30000.0
    assert client.post(f"/payments/{pay['id']}/refunds", headers=admin, json={"reason": "Ko'p", "amount": 70000.01}).status_code == 422
    assert client.post(f"/payments/{pay['id']}/refunds", headers=admin, json={"reason": "x", "amount": 1}).status_code == 422   # sabab qisqa
    rest = client.post(f"/payments/{pay['id']}/refunds", headers=admin, json={"reason": "Qolganini ham qaytarish"}).json()     # qolgan qism
    assert rest["refunded_amount"] == 100000.0
    after = client.get(f"/invoices/{inv['id']}", headers=admin).json()
    assert after["status"] == "Issued" and after["balance"] == 100000.0                  # qaytadan to'lash mumkin
    assert client.post(f"/payments/{pay['id']}/refunds", headers=admin, json={"reason": "Yana"}).status_code == 422
    expenses = [t for t in client.get("/finance/transactions", params={"type": "expense"}, headers=admin).json() if "Qaytarish" in t["description"]]
    assert sorted(t["amount"] for t in expenses) == [30000.0, 70000.0] and all(t["category"] == "Qaytarish" for t in expenses)
    audit = client.get("/security/audit", params={"entity_type": "payment", "limit": 50}, headers=admin).json()["items"]
    assert {"create", "refund"} <= {e["action"] for e in audit}
    again = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Card"})
    assert again.status_code == 201


def test_receipt_retry_for_failed_online_style_payment(client, auth):
    """Provayder to'lovi: chek keyin beriladi. Bu yerda to'lovni qo'lda 'Failed' chek holatida yaratib, qayta berishni tekshiramiz."""
    cashier = auth("cashier")
    inv = _issued_invoice(client, auth)
    pay = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"}).json()
    assert client.post(f"/payments/{pay['id']}/receipt", headers=cashier).status_code == 409      # chek allaqachon berilgan
    with SessionLocal() as db:
        db.execute(text("update payments set receipt_status = 'Failed', receipt_id = null where id = :i"), {"i": pay["id"]})
        db.commit()
    fixed = client.post(f"/payments/{pay['id']}/receipt", headers=cashier).json()
    assert fixed["receipt_status"] == "Issued" and fixed["receipt_id"].startswith("MOCK-")
    assert client.post(f"/payments/{pay['id']}/receipt", headers=cashier).status_code == 409      # endi chek bor
