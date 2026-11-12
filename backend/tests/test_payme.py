import base64
import time

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal
from app.services import fiscal, payme
from tests.test_payments import _issued_invoice

KEY = "test-key-123"


pytestmark = pytest.mark.usefixtures("desk")


@pytest.fixture(autouse=True)
def _payme_config(monkeypatch):
    monkeypatch.setattr(settings, "payme_merchant_id", "merchant-1")
    monkeypatch.setattr(settings, "payme_test_key", KEY)
    monkeypatch.setattr(settings, "payme_key", "prod-key-999")
    monkeypatch.setattr(settings, "payme_test_mode", True)


def _auth(key=KEY, login="Paycom"):
    return {"Authorization": "Basic " + base64.b64encode(f"{login}:{key}".encode()).decode()}


def rpc(client, method, params, headers=None, rpc_id=7):
    res = client.post("/payments/payme", headers=_auth() if headers is None else headers,
                      json={"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params})
    assert res.status_code == 200
    return res.json()


def _order(client, auth, price=112000):
    inv = _issued_invoice(client, auth, price=price)
    pay = client.post(f"/invoices/{inv['id']}/payments", headers=auth("cashier"), json={"method": "Payme"})
    assert pay.status_code == 201, pay.text
    return inv, pay.json()


def _params(pay, **extra):
    return {"amount": int(pay["amount"] * 100), "account": {"order_id": pay["id"]}, **extra}


def _create(client, pay, txn="txn-1", at=None):
    return rpc(client, "CreateTransaction", _params(pay, id=txn, time=at or int(time.time() * 1000)))


def test_authentication_required_and_key_by_mode(client, auth):
    _, pay = _order(client, auth)
    for headers in ({}, _auth("wrong"), _auth(login="Other"), _auth("prod-key-999"), {"Authorization": "Basic !!!"}, {"Authorization": "Bearer x"}):
        body = rpc(client, "CheckPerformTransaction", _params(pay), headers=headers)
        assert body["error"]["code"] == -32504 and body["id"] == 7 and set(body["error"]["message"]) == {"ru", "uz", "en"}
    assert "result" in rpc(client, "CheckPerformTransaction", _params(pay))
    settings.payme_test_mode = False                                      # prod rejimida faqat prod kaliti
    assert rpc(client, "CheckPerformTransaction", _params(pay))["error"]["code"] == -32504
    assert "result" in rpc(client, "CheckPerformTransaction", _params(pay), headers=_auth("prod-key-999"))
    settings.payme_key = ""                                               # kalit yo'q: hamma rad etiladi
    assert rpc(client, "CheckPerformTransaction", _params(pay), headers=_auth(""))["error"]["code"] == -32504


def test_protocol_errors(client, auth):
    raw = client.post("/payments/payme", headers=_auth(), content=b"{not json")
    assert raw.status_code == 200 and raw.json()["error"]["code"] == -32700
    assert client.post("/payments/payme", headers=_auth(), json={"id": 1, "method": "X"}).json()["error"]["code"] == -32600
    assert rpc(client, "Nope", {})["error"]["code"] == -32601
    assert rpc(client, "CheckTransaction", {})["error"]["code"] == -32602
    assert client.post("/payments/payme", headers=_auth(), json={"jsonrpc": "2.0", "id": 1, "method": "GetStatement", "params": []}
                       ).json()["error"]["code"] == -32602


def test_checkout_url_encodes_merchant_order_and_tiyin(client, auth):
    _, pay = _order(client, auth, price=150000)
    assert pay["status"] == "Pending" and pay["receipt_id"] is None
    url = pay["checkout_url"]
    assert url.startswith("https://test.paycom.uz/")
    decoded = base64.b64decode(url.rsplit("/", 1)[1]).decode()
    assert f"m=merchant-1;ac.order_id={pay['id']};a=15000000" in decoded
    settings.payme_test_mode = False
    assert client.get(f"/invoices/{pay['invoice_id']}/payments", headers=auth("cashier")).json()[0]["checkout_url"].startswith("https://checkout.paycom.uz/")


def test_full_payment_flow_idempotent_and_books_income_and_receipt(client, auth):
    cashier = auth("cashier")
    inv, pay = _order(client, auth, price=112000)
    check = rpc(client, "CheckPerformTransaction", _params(pay))["result"]
    assert check["allow"] is True and check["detail"]["receipt_type"] == 0
    items = check["detail"]["items"]
    assert sum(i["price"] * i["count"] for i in items) == 11200000                       # chek qatorlari = to'lov summasi (tiyin)
    assert items[0]["code"] == "09302001001000000" and items[0]["package_code"] == "1500364" and items[0]["vat_percent"] == 12
    created = _create(client, pay)["result"]
    assert created["state"] == 1 and created["transaction"] == pay["id"]
    assert _create(client, pay)["result"] == created                                       # idempotent
    mid = client.get(f"/invoices/{inv['id']}", headers=cashier).json()
    assert mid["status"] == "Issued" and mid["paid_amount"] == 0.0 and mid["balance"] == 112000.0     # pul hali kelmagan
    done = rpc(client, "PerformTransaction", {"id": "txn-1"})["result"]
    assert done["state"] == 2 and done["transaction"] == pay["id"] and done["perform_time"] > 0
    assert rpc(client, "PerformTransaction", {"id": "txn-1"})["result"] == done            # idempotent
    after = client.get(f"/invoices/{inv['id']}", headers=cashier).json()
    assert after["status"] == "Paid" and after["paid_amount"] == 112000.0
    paid = client.get(f"/invoices/{inv['id']}/payments", headers=cashier).json()[0]
    assert paid["status"] == "Paid" and paid["receipt_status"] == "Issued" and paid["receipt_id"].startswith("MOCK-") and paid["checkout_url"] is None
    assert paid["provider_txn_id"] == "txn-1"
    tx = [t for t in client.get("/finance/transactions", params={"type": "income"}, headers=cashier).json() if inv["number"] in t["description"]]
    assert len(tx) == 1 and "Payme" in tx[0]["description"]
    chk = rpc(client, "CheckTransaction", {"id": "txn-1"})["result"]
    assert chk["state"] == 2 and chk["perform_time"] == done["perform_time"] and chk["cancel_time"] == 0 and chk["reason"] is None
    stmt = rpc(client, "GetStatement", {"from": 0, "to": int(time.time() * 1000) + 10000})["result"]["transactions"]
    assert [t["id"] for t in stmt] == ["txn-1"] and stmt[0]["amount"] == 11200000 and stmt[0]["account"] == {"order_id": pay["id"]}
    assert rpc(client, "GetStatement", {"from": 1, "to": 2})["result"]["transactions"] == []
    assert rpc(client, "CheckPerformTransaction", _params(pay))["error"]["code"] == -31051   # to'langan: qayta to'lab bo'lmaydi


def test_wrong_amount_unknown_order_and_busy(client, auth):
    _, pay = _order(client, auth)
    assert rpc(client, "CheckPerformTransaction", {**_params(pay), "amount": 100})["error"]["code"] == -31001
    assert rpc(client, "CreateTransaction", {**_params(pay, id="a", time=1), "amount": 11200001})["error"]["code"] == -31001
    assert rpc(client, "CheckPerformTransaction", {"amount": 100, "account": {"order_id": "00000000-0000-0000-0000-000000000000"}}
               )["error"]["code"] == -31050
    assert rpc(client, "CheckPerformTransaction", {"amount": 100, "account": {"order_id": "bad"}})["error"]["code"] == -31050
    assert rpc(client, "CheckPerformTransaction", {"amount": 100})["error"]["code"] == -31050
    assert rpc(client, "CheckPerformTransaction", {**_params(pay), "amount": "x"})["error"]["code"] == -31001
    assert "result" in _create(client, pay, "first")
    busy = _create(client, pay, "second")
    assert busy["error"]["code"] == -31099 and busy["error"]["data"] == "order_id"
    assert rpc(client, "CheckPerformTransaction", _params(pay))["error"]["code"] == -31051          # yaratilgan: boshqa tranzaksiya kerak emas


def test_cancel_before_perform_frees_balance_and_blocks_perform(client, auth):
    cashier = auth("cashier")
    inv, pay = _order(client, auth)
    _create(client, pay)
    assert client.get(f"/invoices/{inv['id']}", headers=cashier).json()["balance"] == 112000.0        # Pending to'lov hisobga olinmaydi
    other = client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash", "amount": 1})
    assert other.status_code == 422                                                                    # summa Pending bilan band
    canceled = rpc(client, "CancelTransaction", {"id": "txn-1", "reason": 4})["result"]
    assert canceled["state"] == -1 and canceled["cancel_time"] > 0
    assert rpc(client, "CancelTransaction", {"id": "txn-1", "reason": 4})["result"] == canceled        # idempotent
    chk = rpc(client, "CheckTransaction", {"id": "txn-1"})["result"]
    assert chk["state"] == -1 and chk["reason"] == 4
    assert rpc(client, "PerformTransaction", {"id": "txn-1"})["error"]["code"] == -31008
    assert _create(client, pay, "txn-1")["error"]["code"] == -31008
    assert client.get(f"/invoices/{inv['id']}/payments", headers=cashier).json()[0]["status"] == "Cancelled"
    assert client.post(f"/invoices/{inv['id']}/payments", headers=cashier, json={"method": "Cash"}).status_code == 201   # qoldiq bo'shadi


def test_cancel_after_perform_refunds_fully(client, auth):
    cashier, admin = auth("cashier"), auth("admin")
    inv, pay = _order(client, auth)
    _create(client, pay)
    rpc(client, "PerformTransaction", {"id": "txn-1"})
    canceled = rpc(client, "CancelTransaction", {"id": "txn-1", "reason": 5})["result"]
    assert canceled["state"] == -2
    assert rpc(client, "CancelTransaction", {"id": "txn-1", "reason": 5})["result"] == canceled
    assert rpc(client, "CheckTransaction", {"id": "txn-1"})["result"]["state"] == -2
    after = client.get(f"/invoices/{inv['id']}", headers=admin).json()
    assert after["status"] == "Issued" and after["refunded_amount"] == 112000.0 and after["balance"] == 112000.0
    payment = client.get(f"/invoices/{inv['id']}/payments", headers=cashier).json()[0]
    assert payment["refunded_amount"] == 112000.0 and payment["refunds"][0]["receipt_id"].startswith("MOCK-")
    exp = [t for t in client.get("/finance/transactions", params={"type": "expense"}, headers=admin).json() if "Qaytarish" in t["description"]]
    assert [t["amount"] for t in exp] == [112000.0]
    # cashier Payme to'lovini qo'lda qaytara olmaydi (provayder orqali)
    assert client.post(f"/payments/{payment['id']}/refunds", headers=admin, json={"reason": "Qo'lda"}).status_code in (409, 422)


def test_timeout_cancels_with_reason_4(client, auth):
    _, pay = _order(client, auth)
    _create(client, pay)
    with SessionLocal() as db:
        old = int(time.time() * 1000) - payme.TIMEOUT_MS - 60000
        db.execute(text("update payments set provider_data = jsonb_set(provider_data, '{create_time}', to_jsonb(cast(:t as bigint))) "
                        "where id = :i"), {"t": old, "i": pay["id"]})
        db.commit()
    assert rpc(client, "PerformTransaction", {"id": "txn-1"})["error"]["code"] == -31008
    chk = rpc(client, "CheckTransaction", {"id": "txn-1"})["result"]
    assert chk["state"] == -1 and chk["reason"] == 4


def test_unknown_transaction_and_params(client, auth):
    assert rpc(client, "PerformTransaction", {"id": "nope"})["error"]["code"] == -31003
    assert rpc(client, "CancelTransaction", {"id": "nope", "reason": 1})["error"]["code"] == -31003
    assert rpc(client, "CheckTransaction", {"id": "nope"})["error"]["code"] == -31003
    assert rpc(client, "PerformTransaction", {})["error"]["code"] == -32602
    _, pay = _order(client, auth)
    assert rpc(client, "CreateTransaction", _params(pay, id="t", time="x"))["error"]["code"] == -32602
    _create(client, pay)
    assert rpc(client, "CancelTransaction", {"id": "txn-1", "reason": "x"})["error"]["code"] == -32602


def test_receipt_failure_after_money_received_is_retriable(client, auth, monkeypatch):
    cashier = auth("cashier")
    inv, pay = _order(client, auth)
    _create(client, pay)

    class Broken:
        def sale(self, receipt):
            raise fiscal.FiscalError("down")

        def refund(self, receipt, original):
            raise fiscal.FiscalError("down")

    monkeypatch.setattr(fiscal, "_adapter", Broken())
    assert rpc(client, "PerformTransaction", {"id": "txn-1"})["result"]["state"] == 2          # pul olingan: Payme'ga xato qaytarilmaydi
    p = client.get(f"/invoices/{inv['id']}/payments", headers=cashier).json()[0]
    assert p["status"] == "Paid" and p["receipt_status"] == "Failed" and p["receipt_id"] is None
    monkeypatch.setattr(fiscal, "_adapter", fiscal.MockFiscalAdapter())
    fixed = client.post(f"/payments/{p['id']}/receipt", headers=cashier).json()
    assert fixed["receipt_status"] == "Issued" and fixed["receipt_id"].startswith("MOCK-")


def test_cashier_can_cancel_only_untouched_pending(client, auth):
    cashier = auth("cashier")
    inv, pay = _order(client, auth)
    gone = client.post(f"/payments/{pay['id']}/cancel", headers=cashier).json()
    assert gone["status"] == "Cancelled"
    assert client.post(f"/payments/{pay['id']}/cancel", headers=cashier).status_code == 409
    assert rpc(client, "CheckPerformTransaction", _params(pay))["error"]["code"] == -31051
    _, pay2 = _order(client, auth, price=90000)
    _create(client, pay2, "txn-9")
    assert client.post(f"/payments/{pay2['id']}/cancel", headers=cashier).status_code == 409   # Payme tranzaksiyasi boshlangan
    assert inv
