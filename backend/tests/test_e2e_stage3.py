"""3-bosqich "Shart"i: har bir to'lov fiskal chek bilan yopiladi (mock'da chek ID saqlanadi).

Butun moliya zanjiri: narxnoma (MXIK/QQS) -> hisob-faktura (chegirma) -> smena -> naqd+karta (qisman) -> Payme va Click (mock imzo/kalit) ->
qaytarish -> shifokor foizi (hisoblash va teskari yozuv) -> Z-hisobot -> oylik yopish. Hamma Paid to'lovda `receipt_id` bor,
moliya yozuvlari to'lov va qaytarishlarga aniq mos.
"""
import base64
import hashlib
import time
from datetime import date

from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal
from tests.test_patients import NEW

DOCTOR = "Dr. Behruz Rustamov"
PAYME_KEY, CLICK_SECRET = "e2e-payme-key", "e2e-click-secret"


def _payme(client, method, params):
    auth = "Basic " + base64.b64encode(f"Paycom:{PAYME_KEY}".encode()).decode()
    body = client.post("/payments/payme", headers={"Authorization": auth}, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).json()
    assert "error" not in body, body
    return body["result"]


def _click(client, pay, action, trans, **extra):
    p = {"click_trans_id": trans, "service_id": "555", "click_paydoc_id": "1", "merchant_trans_id": pay["id"], "amount": f"{pay['amount']:.2f}",
         "action": str(action), "error": "0", "sign_time": "2026-11-12 10:00:00", **extra}
    if action == 1:
        p["merchant_prepare_id"] = pay["id"]
    parts = [p["click_trans_id"], p["service_id"], CLICK_SECRET, p["merchant_trans_id"]] + ([p["merchant_prepare_id"]] if action == 1 else []) \
        + [p["amount"], p["action"], p["sign_time"]]
    p["sign_string"] = hashlib.md5("".join(parts).encode()).hexdigest()
    body = client.post("/payments/click", data=p).json()
    assert body["error"] == 0, body
    return body


def test_every_payment_is_closed_with_a_fiscal_receipt_end_to_end(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "payme_merchant_id", "m-e2e")
    monkeypatch.setattr(settings, "payme_test_key", PAYME_KEY)
    monkeypatch.setattr(settings, "payme_test_mode", True)
    monkeypatch.setattr(settings, "click_service_id", "555")
    monkeypatch.setattr(settings, "click_merchant_id", "888")
    monkeypatch.setattr(settings, "click_test_secret_key", CLICK_SECRET)
    monkeypatch.setattr(settings, "click_test_mode", True)
    admin, cashier = auth("admin"), auth("cashier")
    month = date.today().strftime("%Y-%m")

    # 1. Narxnoma: MXIK/package_code/QQS; kodsiz xizmat sotilmaydi
    svc = client.post("/services", headers=admin, json={"name": "E2E konsultatsiya", "price": 200000, "mxik": "09302001001000000",
                                                       "package_code": "1500364", "vat_percent": 12}).json()
    lab = client.post("/services", headers=admin, json={"name": "E2E tahlil", "price": 100000, "mxik": "09302001001000001",
                                                       "package_code": "1500364", "vat_percent": 0}).json()
    bare = client.post("/services", headers=admin, json={"name": "E2E kodsiz", "price": 1000}).json()
    doctor_id = next(s["id"] for s in client.get("/staff", headers=admin).json() if s["name"] == DOCTOR)
    pid = client.post("/patients", json={**NEW, "name": "E2E Bemor"}, headers=admin).json()["id"]
    assert client.post("/invoices", headers=cashier, json={"patient_id": pid, "lines": [{"service_id": bare["id"]}]}).status_code == 422
    assert client.post("/commission-rules", headers=admin, json={"kind": "Percent", "percent": 10, "doctor_id": doctor_id,
                                                                 "base": "WithVat", "valid_from": "2026-01-01"}).status_code == 201

    # 2. Smena ochiladi (kassir va admin)
    shift = client.post("/cash-shifts/open", json={"opening_cash": 100000}, headers=cashier).json()
    client.post("/cash-shifts/open", json={"opening_cash": 0}, headers=admin)

    def invoice(lines, **kw):
        res = client.post("/invoices", headers=cashier, json={"patient_id": pid, "doctor_id": doctor_id, "lines": lines, "issue": True, **kw})
        assert res.status_code == 201, res.text
        return res.json()

    # 3. Naqd + karta (qisman, chegirma bilan): 2*200000 + 100000 = 500000, 10% chegirma = 450000
    inv1 = invoice([{"service_id": svc["id"], "quantity": 2}, {"service_id": lab["id"]}], discount_percent=10, discount_reason="Doimiy mijoz")
    assert inv1["total"] == 450000.0 and inv1["discount_total"] == 50000.0
    cash = client.post(f"/invoices/{inv1['id']}/payments", headers=cashier, json={"method": "Cash", "amount": 150000}).json()
    client.post(f"/invoices/{inv1['id']}/payments", headers=cashier, json={"method": "Card", "reference": "TERM-77"})
    assert client.get(f"/invoices/{inv1['id']}", headers=cashier).json()["status"] == "Paid"

    # 4. Payme (JSON-RPC)
    inv2 = invoice([{"service_id": svc["id"]}])
    pm = client.post(f"/invoices/{inv2['id']}/payments", headers=cashier, json={"method": "Payme"}).json()
    assert pm["status"] == "Pending" and pm["checkout_url"] and pm["receipt_id"] is None                   # chek pul kelgunga qadar yo'q
    tiyin = int(pm["amount"] * 100)
    now = int(time.time() * 1000)
    assert _payme(client, "CheckPerformTransaction", {"amount": tiyin, "account": {"order_id": pm["id"]}})["allow"] is True
    _payme(client, "CreateTransaction", {"id": "e2e-pm-1", "time": now, "amount": tiyin, "account": {"order_id": pm["id"]}})
    assert _payme(client, "PerformTransaction", {"id": "e2e-pm-1"})["state"] == 2

    # 5. Click (Prepare/Complete)
    inv3 = invoice([{"service_id": lab["id"]}])
    ck = client.post(f"/invoices/{inv3['id']}/payments", headers=cashier, json={"method": "Click"}).json()
    _click(client, ck, 0, "c-1")
    _click(client, ck, 1, "c-1")

    # 6. Shart: har bir Paid to'lovda fiskal chek ID bor (bazada ham)
    all_payments = [p for inv in (inv1, inv2, inv3) for p in client.get(f"/invoices/{inv['id']}/payments", headers=cashier).json()]
    paid = [p for p in all_payments if p["status"] == "Paid"]
    assert {p["method"] for p in paid} == {"Cash", "Card", "Payme", "Click"} and len(paid) == 4
    assert all(p["receipt_status"] == "Issued" and p["receipt_id"].startswith("MOCK-") for p in paid)
    assert len({p["receipt_id"] for p in paid}) == 4                                                       # har chek noyob
    with SessionLocal() as db:
        assert db.execute(text("select count(*) from payments where status = 'Paid' and (receipt_id is null or receipt_status <> 'Issued')")).scalar() == 0
        # chek qatorlari to'lov summasiga teng (tiyin), har qatorda MXIK/package_code/QQS
        rows = db.execute(text("select (receipt_data->>'total_tiyin')::bigint, (select sum((i->>'amount_tiyin')::bigint) from jsonb_array_elements(receipt_data->'items') i), "
                               "(select bool_and(i->>'mxik' ~ '^[0-9]{17}$' and i->>'package_code' is not null and i->>'vat_percent' is not null) "
                               "from jsonb_array_elements(receipt_data->'items') i) from payments where status = 'Paid'")).all()
        assert rows and all(total == items and ok for total, items, ok in rows)

    # 7. Qaytarish: admin smenasidan naqd to'lovning bir qismi; qaytarish cheki, xarajat, foiz teskari
    refund = client.post(f"/payments/{cash['id']}/refunds", headers=admin, json={"reason": "Xizmat ko'rsatilmadi", "amount": 50000})
    assert refund.status_code == 201 and refund.json()["refunds"][0]["receipt_id"].startswith("MOCK-")
    assert client.get(f"/invoices/{inv1['id']}", headers=cashier).json()["status"] == "PartiallyPaid"
    # Click/Payme to'lovini qo'lda qaytarib bo'lmaydi; Payme bekor qilishi (-2) avtomatik qaytaradi
    assert client.post(f"/payments/{pm['id']}/refunds", headers=admin, json={"reason": "Qo'lda"}).status_code == 409
    assert _payme(client, "CancelTransaction", {"id": "e2e-pm-1", "reason": 5})["state"] == -2
    assert client.get(f"/invoices/{inv2['id']}", headers=cashier).json()["status"] == "Issued"

    # 8. Moliya yozuvlari to'lov va qaytarishlarga aniq mos
    tx = client.get("/finance/transactions", headers=admin).json()
    income = sum(t["amount"] for t in tx if t["category"] == "Xizmat to'lovi")
    expense = sum(t["amount"] for t in tx if t["category"] == "Qaytarish")
    assert income == 150000 + 300000 + 200000 + 100000 and expense == 50000 + 200000

    # 9. Shifokor foizi: inv1 (qisman) + inv3; qaytarishlar teskari
    entries = client.get("/commissions/entries", params={"month": month, "doctor_id": doctor_id}, headers=admin).json()
    accrual = sum(e["amount"] for e in entries if e["kind"] == "Accrual")
    reversal = sum(e["amount"] for e in entries if e["kind"] == "Reversal")
    assert accrual == 45000 + 20000 + 10000 and reversal == -(5000 + 20000)        # (inv1 450000, inv2 200000, inv3 100000) * 10%
    report = client.get("/commissions/report", params={"month": month}, headers=admin).json()
    assert report["doctors"][0]["net"] == accrual + reversal == report["total_net"] == 50000

    # 10. Z-hisobot: kutilgan naqd = 100000 + 150000 - 0 (qaytarish admin smenasida); farq; ketma-ket Z
    x = client.get(f"/cash-shifts/{shift['shift_id']}/report", headers=cashier).json()
    assert x["cash"]["payments_total"] == 150000.0 and x["card"]["payments_total"] == 300000.0 and x["expected_cash"] == 250000.0
    assert x["online"]["payme"]["payments_count"] == 1 and x["online"]["click"]["payments_total"] == 100000.0 and x["receipts_missing"] == 0
    z = client.post(f"/cash-shifts/{shift['shift_id']}/close", headers=cashier, json={"counted_cash": 250000}).json()
    assert z["z_number"].startswith("Z-") and z["difference"] == 0.0
    admin_shift = client.get("/cash-shifts/current", headers=admin).json()
    assert admin_shift["cash"]["refunds_total"] == 50000.0 and admin_shift["expected_cash"] == -50000.0

    # 11. Oylik yopish
    settle = client.post("/commissions/settle", headers=admin, json={"month": month, "doctor_id": doctor_id})
    assert settle.status_code == 201 and settle.json()["amount"] == accrual + reversal
