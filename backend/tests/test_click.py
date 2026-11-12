import hashlib
import re

import pytest

from app.core.config import settings
from app.services import click, fiscal
from tests.test_payments import _issued_invoice

SECRET = "click-test-secret"


@pytest.fixture(autouse=True)
def _click_config(monkeypatch):
    monkeypatch.setattr(settings, "click_service_id", "12345")
    monkeypatch.setattr(settings, "click_merchant_id", "777")
    monkeypatch.setattr(settings, "click_test_secret_key", SECRET)
    monkeypatch.setattr(settings, "click_secret_key", "prod-secret")
    monkeypatch.setattr(settings, "click_test_mode", True)


def _sig(p, complete, secret=SECRET):
    parts = [p["click_trans_id"], p["service_id"], secret, p["merchant_trans_id"]]
    if complete:
        parts.append(p["merchant_prepare_id"])
    parts += [p["amount"], p["action"], p["sign_time"]]
    return hashlib.md5("".join(parts).encode()).hexdigest()


def req(pay, action, trans="9001", prepare_id="", amount=None, secret=SECRET, **over):
    p = {"click_trans_id": trans, "service_id": "12345", "click_paydoc_id": "555", "merchant_trans_id": pay["id"],
         "amount": amount if amount is not None else f"{pay['amount']:.2f}", "action": str(action), "error": "0",
         "error_note": "Success", "sign_time": "2026-11-12 10:00:00"}
    if action == 1:
        p["merchant_prepare_id"] = prepare_id or pay["id"]
    p.update(over)
    p["sign_string"] = _sig(p, action == 1, secret) if "sign_string" not in over else over["sign_string"]
    return p


def call(client, params, as_json=False):
    res = client.post("/payments/click", json=params) if as_json else client.post("/payments/click", data=params)
    assert res.status_code == 200
    return res.json()


def _order(client, auth, price=112000):
    inv = _issued_invoice(client, auth, price=price)
    pay = client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json={"method": "Click"})
    assert pay.status_code == 201, pay.text
    return inv, pay.json()


def test_checkout_url_and_pending_reserve(client, auth):
    inv, pay = _order(client, auth, price=150000)
    assert pay["status"] == "Pending" and pay["receipt_id"] is None
    assert pay["checkout_url"] == (f"https://my.click.uz/services/pay?service_id=12345&merchant_id=777&amount=150000.00"
                                   f"&transaction_param={pay['id']}")
    assert client.get(f"/invoices/{inv['id']}", headers=auth("cashier")).json()["paid_amount"] == 0.0
    assert client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json={"method": "Cash"}).status_code == 409   # summa Click bilan band


def test_signature_checked_first_and_empty_secret_never_valid(client, auth):
    _, pay = _order(client, auth)
    bad = call(client, req(pay, 0, sign_string="0" * 32))
    assert bad["error"] == -1 and bad["error_note"] == "SIGN CHECK FAILED!" and bad["click_trans_id"] == "9001"
    assert call(client, req(pay, 0, secret="prod-secret"))["error"] == -1                    # test rejimida prod kaliti emas
    assert call(client, req(pay, 0, amount="1.00", sign_string="x"))["error"] == -1          # imzo summadan oldin
    settings.click_test_mode = False
    assert call(client, req(pay, 0))["error"] == -1                                          # prod rejimida test kaliti emas
    assert call(client, req(pay, 0, secret="prod-secret"))["error"] == 0
    settings.click_secret_key = ""                                                           # bo'sh kalit: soxta imzo ham o'tmaydi
    forged = req(pay, 0, secret="")
    assert call(client, forged)["error"] == -1
    assert click.valid_sign(forged, False) is False


def test_prepare_complete_flow_idempotent_and_books_payment(client, auth):
    cashier = auth("cashier")
    inv, pay = _order(client, auth, price=112000)
    prep = call(client, req(pay, 0))
    assert prep["error"] == 0 and prep["merchant_prepare_id"] == pay["id"] and prep["merchant_trans_id"] == pay["id"]
    assert call(client, req(pay, 0)) == prep                                                  # idempotent Prepare
    assert client.get(f"/invoices/{inv['id']}", headers=cashier).json()["status"] == "Issued"
    done = call(client, req(pay, 1, prepare_id=prep["merchant_prepare_id"]))
    assert done["error"] == 0 and done["merchant_confirm_id"] == pay["id"]
    again = call(client, req(pay, 1, prepare_id=prep["merchant_prepare_id"]))
    assert again["error"] == -4 and again["error_note"] == "Already paid"                    # qayta Complete: allaqachon to'langan
    assert call(client, req(pay, 0, trans="9002"))["error"] == -4                            # to'langan buyurtmaga Prepare ham -4
    paid = client.get(f"/invoices/{inv['id']}/payments", headers=cashier).json()[0]
    assert paid["status"] == "Paid" and paid["receipt_status"] == "Issued" and paid["receipt_id"].startswith("MOCK-")
    assert paid["provider_txn_id"] == "9001" and paid["checkout_url"] is None
    assert client.get(f"/invoices/{inv['id']}", headers=cashier).json()["status"] == "Paid"
    tx = [t for t in client.get("/finance/transactions", params={"type": "income"}, headers=cashier).json() if inv["number"] in t["description"]]
    assert len(tx) == 1 and "Click" in tx[0]["description"] and tx[0]["amount"] == 112000.0


def test_json_body_and_amount_formats(client, auth):
    _, pay = _order(client, auth, price=112000)
    assert call(client, req(pay, 0, amount="112000"), as_json=True)["error"] == 0             # kasrsiz summa ham
    _, pay2 = _order(client, auth, price=90000)
    assert call(client, req(pay2, 0, trans="9002", amount="90000.00"))["error"] == 0
    assert call(client, req(pay2, 0, trans="9001", amount="90000.00"))["error"] == -8        # boshqa buyurtmaning click_trans_id si


def test_errors_amount_order_action_transaction(client, auth):
    _, pay = _order(client, auth)
    assert call(client, req(pay, 0, amount="111999.99"))["error"] == -2
    assert call(client, req(pay, 0, amount="abc"))["error"] == -2
    assert call(client, req(pay, 0, amount="112000.001"))["error"] == -2                      # tiyindan kichik kasr
    ghost = {**pay, "id": "00000000-0000-0000-0000-000000000000"}
    assert call(client, req(ghost, 0))["error"] == -5
    assert call(client, req({**pay, "id": "not-a-uuid"}, 0))["error"] == -5
    assert call(client, req(pay, 2))["error"] == -3 and call(client, req(pay, 7))["error"] == -3
    assert call(client, req(pay, 0, service_id="999"))["error"] == -8
    # Complete Prepare'siz / noto'g'ri prepare_id / boshqa trans
    assert call(client, req(pay, 1))["error"] == -6
    assert call(client, req(pay, 0))["error"] == 0
    assert call(client, req(pay, 1, prepare_id="wrong"))["error"] == -6
    assert call(client, req(pay, 1, trans="other"))["error"] == -6
    assert call(client, req(pay, 1, amount="1.00"))["error"] == -2
    assert call(client, req(pay, 0, trans="9002"))["error"] == -8                             # buyurtma boshqa tranzaksiya bilan band


def test_click_failure_cancels_order(client, auth):
    cashier = auth("cashier")
    inv, pay = _order(client, auth)
    call(client, req(pay, 0))
    failed = call(client, req(pay, 1, error="-5017", error_note="Not enough funds"))
    assert failed["error"] == -9 and failed["error_note"] == "Transaction cancelled"
    p = client.get(f"/invoices/{inv['id']}/payments", headers=cashier).json()[0]
    assert p["status"] == "Cancelled"
    assert call(client, req(pay, 0, trans="9005"))["error"] == -9                             # bekor qilingan buyurtma
    assert call(client, req(pay, 1))["error"] == -9
    assert client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"}).status_code == 201   # qoldiq bo'shadi


def test_prepare_error_from_click_cancels(client, auth):
    inv, pay = _order(client, auth)
    assert call(client, req(pay, 0, error="-1"))["error"] == -9
    assert client.get(f"/invoices/{inv['id']}/payments", headers=auth("cashier")).json()[0]["status"] == "Cancelled"


def test_receipt_failure_keeps_payment_and_is_retriable(client, auth, monkeypatch):
    cashier = auth("cashier")
    inv, pay = _order(client, auth)
    call(client, req(pay, 0))

    class Broken:
        def sale(self, receipt):
            raise fiscal.FiscalError("down")

        def refund(self, receipt, original):
            raise fiscal.FiscalError("down")

    monkeypatch.setattr(fiscal, "_adapter", Broken())
    assert call(client, req(pay, 1))["error"] == 0                                           # pul olindi: Click'ga xato qaytmaydi
    p = client.get(f"/invoices/{inv['id']}/payments", headers=cashier).json()[0]
    assert p["status"] == "Paid" and p["receipt_status"] == "Failed"
    monkeypatch.setattr(fiscal, "_adapter", fiscal.MockFiscalAdapter())
    assert client.post(f"/payments/{p['id']}/receipt", headers=cashier).json()["receipt_status"] == "Issued"
    # Click to'lovini kassir/admin qo'lda qaytara olmaydi
    assert client.post(f"/payments/{p['id']}/refunds", headers=auth("admin"), json={"reason": "Qo'lda"}).status_code == 409


def test_payme_and_click_use_same_money_conversion():
    import inspect

    from app.services import money, payme
    for module in (payme, click):
        src = inspect.getsource(module)
        assert "to_tiyin" in src and not re.search(r"[*/]\s*100\b", src) and "Decimal(100)" not in src
    assert money.to_tiyin("150000.00") == 15000000
