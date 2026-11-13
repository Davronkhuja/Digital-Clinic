from datetime import date

import pytest

from tests.test_commissions import DOC1, _doctor, _invoice, _pay, _rule, _service

pytestmark = pytest.mark.usefixtures("desk")
MONTH = date.today().strftime("%Y-%m")


def _earn(client, auth, price=1000000, percent=10):
    d1 = _doctor(client, auth)
    svc = _service(client, auth, f"Payout {price}", price, vat=0)
    _rule(client, auth, percent=percent)
    _pay(client, auth, _invoice(client, auth, [{"service_id": svc["id"], "doctor_id": d1}]))
    return d1


def _settle(client, auth, d1):
    res = client.post("/commissions/settle", headers=auth("admin"), json={"month": MONTH, "doctor_id": d1})
    assert res.status_code == 201, res.text
    return res.json()


def test_settle_creates_draft_payout_and_flow_draft_approved_paid_transfer(client, auth):
    admin = auth("admin")
    d1 = _earn(client, auth)                                                    # 100000 foiz
    s = _settle(client, auth, d1)
    assert s["payout_id"] and s["payout_status"] == "Draft"
    payouts = client.get("/commission-payouts", headers=admin).json()
    p = payouts[0]
    assert (p["status"], p["amount"], p["doctor"], p["month"]) == ("Draft", 100000.0, DOC1, MONTH)
    assert client.post(f"/commission-payouts/{p['id']}/pay", headers=admin, json={"method": "Transfer"}).status_code == 409       # tasdiqlanmagan
    assert client.post(f"/commission-payouts/{p['id']}/approve", headers=auth("doctor")).status_code == 403
    appr = client.post(f"/commission-payouts/{p['id']}/approve", headers=admin).json()
    assert appr["status"] == "Approved" and appr["approved_by"] == "Admin User" and appr["approved_at"]
    assert client.post(f"/commission-payouts/{p['id']}/approve", headers=admin).status_code == 409
    paid = client.post(f"/commission-payouts/{p['id']}/pay", headers=admin, json={"method": "Transfer", "reference": "PP-123"})
    assert paid.status_code == 200 and paid.json()["status"] == "Paid" and paid.json()["pay_method"] == "Transfer"
    assert client.post(f"/commission-payouts/{p['id']}/pay", headers=admin, json={"method": "Transfer"}).status_code == 409        # qayta to'lab bo'lmaydi
    exp = [t for t in client.get("/finance/transactions", params={"type": "expense"}, headers=admin).json() if t["category"] == "Shifokor foizi"]
    assert len(exp) == 1 and exp[0]["amount"] == 100000.0
    x = client.get("/cash-shifts/current", headers=admin).json()
    assert x["payouts"]["total"] == 0.0                                          # o'tkazma kassaga tegmaydi
    assert [s["payout_status"] for s in client.get("/commissions/settlements", headers=admin).json()] == ["Paid"]
    audit = client.get("/security/audit", params={"entity_type": "commission_payout", "limit": 10}, headers=admin).json()["items"]
    assert {"update", "pay"} <= {e["action"] for e in audit}


def test_cash_payout_rejected_when_drawer_has_too_little_cash(client, auth):
    admin = auth("admin")
    d1 = _earn(client, auth)
    _settle(client, auth, d1)
    pid = client.get("/commission-payouts", headers=admin).json()[0]["id"]
    client.post(f"/commission-payouts/{pid}/approve", headers=admin)
    short = client.post(f"/commission-payouts/{pid}/pay", headers=admin, json={"method": "Cash"})          # admin kassasi bo'sh
    assert short.status_code == 422 and "yetarli emas" in short.json()["detail"]
    assert client.get("/commission-payouts", headers=admin).json()[0]["status"] == "Approved"               # hujjat o'zgarmadi


def test_cash_payout_success_reduces_expected_cash(client, auth):
    admin = auth("admin")
    d1 = _earn(client, auth)
    _settle(client, auth, d1)
    pid = client.get("/commission-payouts", headers=admin).json()[0]["id"]
    client.post(f"/commission-payouts/{pid}/approve", headers=admin)
    from tests.test_shifts import _issued
    inv = _issued(client, auth, 300000, name="Naqd 300")
    client.post(f"/invoices/{inv['id']}/payments", headers=admin, json={"method": "Cash"})
    shift = client.get("/cash-shifts/current", headers=admin).json()
    assert shift["expected_cash"] == 300000.0
    res = client.post(f"/commission-payouts/{pid}/pay", headers=admin, json={"method": "Cash"})
    assert res.status_code == 200 and res.json()["status"] == "Paid"
    x = client.get(f"/cash-shifts/{shift['shift_id']}/report", headers=admin).json()
    assert x["payouts"] == {"count": 1, "total": 100000.0} and x["expected_cash"] == 200000.0
    moves = client.get(f"/cash-shifts/{shift['shift_id']}/movements", headers=admin).json()
    assert [(m["kind"], m["amount"], m["counterparty"]) for m in moves] == [("Payout", 100000.0, DOC1)]
    z = client.post(f"/cash-shifts/{shift['shift_id']}/close", headers=admin, json={"counted_cash": 200000}).json()
    assert z["difference"] == 0.0 and z["payouts"]["total"] == 100000.0


def test_cash_payout_needs_open_shift_and_permission(client, auth):
    d1 = _earn(client, auth)
    _settle(client, auth, d1)
    admin = auth("admin")
    pid = client.get("/commission-payouts", headers=admin).json()[0]["id"]
    client.post(f"/commission-payouts/{pid}/approve", headers=admin)
    assert client.post(f"/commission-payouts/{pid}/pay", headers=auth("cashier"), json={"method": "Cash"}).status_code == 403   # commissions:pay yo'q
    shift = client.get("/cash-shifts/current", headers=admin).json()
    client.post(f"/cash-shifts/{shift['shift_id']}/close", headers=admin, json={"counted_cash": 0})
    no_shift = client.post(f"/commission-payouts/{pid}/pay", headers=admin, json={"method": "Cash"})
    assert no_shift.status_code == 409 and "smena" in no_shift.json()["detail"].lower()
    assert client.post(f"/commission-payouts/{pid}/pay", headers=admin, json={"method": "Transfer"}).status_code == 200            # o'tkazma smenasiz mumkin


def test_no_payout_for_non_positive_month_and_doctor_scope(client, auth):
    d1 = _earn(client, auth, price=100000)
    # to'liq qaytarish: sof nol
    invs = client.get("/invoices", headers=auth("admin")).json()
    pay_id = client.get(f"/invoices/{invs[0]['id']}/payments", headers=auth("admin")).json()[0]["id"]
    client.post(f"/payments/{pay_id}/refunds", headers=auth("admin"), json={"reason": "To'liq qaytarish"})
    s = _settle(client, auth, d1)
    assert s["amount"] == 0.0 and s["payout_id"] is None and s["payout_status"] is None
    assert client.get("/commission-payouts", headers=auth("admin")).json() == []
