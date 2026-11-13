import io

from pypdf import PdfReader

from tests.test_shifts import _issued, _open


def _pay_cash(client, auth, price, role="cashier"):
    inv = _issued(client, auth, price, name=f"Inkassatsiya {price}")
    assert client.post(f"/invoices/{inv['id']}/payments", headers=auth(role), json={"method": "Cash"}).status_code == 201


def test_withdrawal_reduces_expected_cash_and_appears_in_z(client, auth):
    shift = _open(client, auth, "admin", 100000)                       # admin: finance:cash_withdrawal bor
    _open(client, auth, "cashier", 0)
    _pay_cash(client, auth, 400000, "cashier")                          # kassir smenasi
    sid = shift["shift_id"]
    res = client.post(f"/cash-shifts/{sid}/withdrawals", headers=auth("admin"), json={"amount": 60000, "recipient": "Inkassator Karimov", "note": "Bank"})
    assert res.status_code == 201
    m = res.json()
    assert (m["kind"], m["amount"], m["counterparty"], m["note"]) == ("Withdrawal", 60000.0, "Inkassator Karimov", "Bank")
    assert m["by"] == "Admin User"
    x = client.get(f"/cash-shifts/{sid}/report", headers=auth("admin")).json()
    assert x["withdrawals"] == {"count": 1, "total": 60000.0} and x["payouts"] == {"count": 0, "total": 0.0}
    assert x["expected_cash"] == 40000.0                                # 100000 - 60000 (naqd to'lov kassirning smenasida)
    z = client.post(f"/cash-shifts/{sid}/close", headers=auth("admin"), json={"counted_cash": 40000}).json()
    assert z["difference"] == 0.0 and z["withdrawals"]["total"] == 60000.0
    pdf = client.get(f"/cash-shifts/{sid}/z-report/pdf", headers=auth("admin"))
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Inkassatsiya: 1 ta, 60 000.00" in text
    assert client.post(f"/cash-shifts/{sid}/withdrawals", headers=auth("admin"), json={"amount": 1, "recipient": "Kimdir"}).status_code == 409   # yopilgan


def test_withdrawal_limits_permission_and_audit(client, auth):
    shift = _open(client, auth, "admin", 50000)
    sid = shift["shift_id"]
    assert client.post(f"/cash-shifts/{sid}/withdrawals", headers=auth("admin"), json={"amount": 50000.01, "recipient": "Oshiq"}).status_code == 422
    for bad in ({"amount": 0, "recipient": "Nol"}, {"amount": -5, "recipient": "Manfiy"}, {"amount": 10, "recipient": ""}, {"amount": 10}, {"amount": 10.001, "recipient": "Kasr"}):
        assert client.post(f"/cash-shifts/{sid}/withdrawals", headers=auth("admin"), json=bad).status_code == 422, bad
    _open(client, auth, "cashier", 100000)
    cash_shift = client.get("/cash-shifts/current", headers=auth("cashier")).json()["shift_id"]
    assert client.post(f"/cash-shifts/{cash_shift}/withdrawals", headers=auth("cashier"), json={"amount": 10, "recipient": "Kassir"}).status_code == 403   # ruxsat yo'q
    assert client.post(f"/cash-shifts/{cash_shift}/withdrawals", headers=auth("admin"), json={"amount": 70000, "recipient": "Inkassator"}).status_code == 201  # finance:shifts bilan boshqaniki
    ok = client.post(f"/cash-shifts/{sid}/withdrawals", headers=auth("admin"), json={"amount": 50000, "recipient": "Hammasini olish"})
    assert ok.status_code == 201
    assert client.get(f"/cash-shifts/{sid}/report", headers=auth("admin")).json()["expected_cash"] == 0.0
    moves = client.get(f"/cash-shifts/{sid}/movements", headers=auth("admin")).json()
    assert [m["amount"] for m in moves] == [50000.0]
    audit = client.get("/security/audit", params={"entity_type": "cash_movement", "limit": 10}, headers=auth("admin")).json()["items"]
    assert audit and audit[0]["details"]["kind"] == "Withdrawal" and audit[0]["details"]["recipient"]
