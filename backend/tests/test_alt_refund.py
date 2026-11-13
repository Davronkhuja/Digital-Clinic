import pytest

from tests.test_click import _click_config, call, req  # noqa: F401  (autouse fixture)
from tests.test_payments import _issued_invoice

pytestmark = pytest.mark.usefixtures("desk")


def _click_paid(client, auth, price=120000):
    inv = _issued_invoice(client, auth, price=price)
    pay = client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json={"method": "Click"}).json()
    call(client, req(pay, 0))
    call(client, req(pay, 1))
    return inv, pay


def test_click_payment_refunded_by_cash_linked_to_original(client, auth):
    admin = auth("admin")
    inv, pay = _click_paid(client, auth)
    # usul ko'rsatilmasa yoki noto'g'ri bo'lsa
    assert client.post(f"/payments/{pay['id']}/refunds", headers=admin, json={"reason": "Bemor rad etdi"}).status_code == 422
    assert client.post(f"/payments/{pay['id']}/refunds", headers=admin, json={"reason": "Bemor rad etdi", "refund_method": "Click"}).status_code == 422
    assert client.post(f"/payments/{pay['id']}/refunds", headers=auth("cashier"), json={"reason": "Bemor rad etdi", "refund_method": "Cash"}).status_code == 403
    res = client.post(f"/payments/{pay['id']}/refunds", headers=admin, json={"reason": "Bemor rad etdi", "refund_method": "Cash", "amount": 20000})
    assert res.status_code == 201
    out = res.json()
    assert out["method"] == "Click" and out["refunded_amount"] == 20000.0                  # original to'lovga bog'langan
    r = out["refunds"][0]
    assert r["refund_method"] == "Cash" and r["needs_provider_reconcile"] is True and r["receipt_id"].startswith("MOCK-")
    assert client.get(f"/invoices/{inv['id']}", headers=admin).json()["status"] == "PartiallyPaid"
    # naqd qaytarish admin smenasidan chiqadi (kassa hisoboti)
    shift = client.get("/cash-shifts/current", headers=admin).json()
    assert shift["cash"]["refunds_total"] == 20000.0 and shift["card"]["refunds_total"] == 0.0 and shift["expected_cash"] == -20000.0
    # karta bilan qolgani
    card = client.post(f"/payments/{pay['id']}/refunds", headers=admin, json={"reason": "Qolgani", "refund_method": "Card"}).json()
    assert card["refunded_amount"] == 120000.0
    shift = client.get("/cash-shifts/current", headers=admin).json()
    assert shift["card"]["refunds_total"] == 100000.0 and shift["cash"]["refunds_total"] == 20000.0
    # solishtirish ro'yxati va tasdiqlash
    pending = client.get("/payment-refunds/pending-reconcile", headers=admin).json()
    assert len(pending) == 2
    done = client.post(f"/payment-refunds/{pending[0]['id']}/reconcile", headers=admin)
    assert done.status_code == 200 and done.json()["needs_provider_reconcile"] is False
    assert client.post(f"/payment-refunds/{pending[0]['id']}/reconcile", headers=admin).status_code == 409
    assert len(client.get("/payment-refunds/pending-reconcile", headers=admin).json()) == 1
    assert client.get("/payment-refunds/pending-reconcile", headers=auth("cashier")).status_code == 403
    exp = [t for t in client.get("/finance/transactions", params={"type": "expense"}, headers=admin).json() if t["category"] == "Qaytarish"]
    assert sorted(t["amount"] for t in exp) == [20000.0, 100000.0]


def test_cash_card_refunds_unchanged_and_payme_still_via_provider(client, auth):
    admin = auth("admin")
    inv = _issued_invoice(client, auth, price=50000, name="Oddiy qaytarish")
    pay = client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json={"method": "Card"}).json()
    ok = client.post(f"/payments/{pay['id']}/refunds", headers=admin, json={"reason": "Oddiy qaytarish", "refund_method": "Cash"})
    assert ok.status_code == 201 and ok.json()["refunds"][0]["refund_method"] == "Card"             # to'lov usuli bilan (e'tiborsiz)
    assert ok.json()["refunds"][0]["needs_provider_reconcile"] is False
    shift = client.get("/cash-shifts/current", headers=admin).json()
    assert shift["card"]["refunds_total"] == 50000.0
    from sqlalchemy import text

    from app.db.session import SessionLocal
    with SessionLocal() as db:
        db.execute(text("update payments set method = 'Payme' where id = :i"), {"i": pay["id"]})
        db.commit()
    assert client.post(f"/payments/{pay['id']}/refunds", headers=admin, json={"reason": "Payme", "refund_method": "Cash"}).status_code == 409
